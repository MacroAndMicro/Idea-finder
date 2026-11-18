#!/usr/bin/env bash
# IF-84: run the backend API locally against a copy of prod rows.
#
#   scripts/local-api-from-prod.sh            start Postgres + pgvector, rebuild the DB from
#                                             supabase/migrations, load .local-data/*.json,
#                                             start the backend on :8080 and wait for /api/health
#   scripts/local-api-from-prod.sh --db-only  same, but stop after loading the rows (no backend)
#   scripts/local-api-from-prod.sh --stop     stop the backend and Postgres
#
# Idempotent: every start drops and recreates the local database, so re-running reloads
# the current .local-data/ files. Never connects to prod and needs no secret: the rows are
# exported beforehand with the Supabase connector (scripts/export-prod-rows.sql,
# docs/local-api.md). Local credentials only.
#
# Postgres comes from, in order:
#   1. LOCAL_PG_EXTERNAL=1 — an already-running server reached through PGHOST/PGPORT/PGUSER/
#      PGPASSWORD (e.g. CI's pgvector service); the script only creates/drops LOCAL_PG_DB on it.
#   2. Local PostgreSQL binaries (pg_ctl/initdb, PG 16+) with the pgvector extension installed
#      (Debian/Ubuntu: apt-get install postgresql-16-pgvector).
#   3. Docker, image pgvector/pgvector:pg16 (the same pgvector image family CI uses).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${LOCAL_DATA_DIR:-$ROOT/.local-data}"
RUN_DIR="$ROOT/.local-data/run"
MIGRATIONS_DIR="$ROOT/supabase/migrations"

PG_PORT="${LOCAL_PG_PORT:-54329}"
PG_DB="${LOCAL_PG_DB:-idea_finder_local}"
PG_USER="${LOCAL_PG_USER:-idea_finder}"
PG_PASSWORD="${LOCAL_PG_PASSWORD:-idea_finder_local}"   # local-only throwaway password
API_PORT="${LOCAL_API_PORT:-8080}"
HEALTH_TIMEOUT="${LOCAL_API_HEALTH_TIMEOUT:-120}"
DOCKER_IMAGE="pgvector/pgvector:pg16"
DOCKER_NAME="idea-finder-local-pg"

# Tables loaded from $DATA_DIR/<table>.json, in foreign-key order.
TABLES=(opportunity_cards raw_signals ingestion_runs signal_extractions card_signals)

log() { printf '[local-api] %s\n' "$*"; }
die() { printf '[local-api] ERROR: %s\n' "$*" >&2; exit 1; }

# Run a Postgres server binary; initdb/pg_ctl refuse to run as root, so drop to postgres.
as_pg_owner() {
	if [ "$(id -u)" -eq 0 ]; then
		runuser -u postgres -- "$@"
	else
		"$@"
	fi
}

find_pg_bin() {
	local dir
	# shellcheck disable=SC2012  # version dirs are plain numbers
	for dir in "${LOCAL_PG_BIN:-}" $(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -rV) \
		"$(dirname "$(command -v pg_ctl 2>/dev/null || echo /nonexistent/x)")"; do
		if [ -z "$dir" ] || [ ! -x "$dir/pg_ctl" ] || [ ! -x "$dir/initdb" ]; then continue; fi
		local share
		share="$("$dir/pg_config" --sharedir 2>/dev/null || true)"
		if [ -n "$share" ] && [ -f "$share/extension/vector.control" ]; then
			echo "$dir"
			return 0
		fi
	done
	return 1
}

pg_mode() {
	if [ "${LOCAL_PG_EXTERNAL:-0}" = 1 ]; then echo external; return; fi
	if [ -f "$RUN_DIR/pg.mode" ]; then cat "$RUN_DIR/pg.mode"; return; fi
	if find_pg_bin >/dev/null; then echo native; return; fi
	if command -v docker >/dev/null && docker info >/dev/null 2>&1; then echo docker; return; fi
	die "need PostgreSQL 16+ with pgvector (apt-get install postgresql-16-pgvector) or a working docker"
}

# psql against the local server; extra args are passed through. NOTICEs are silenced.
export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"
lpsql() {
	if [ "${LOCAL_PG_EXTERNAL:-0}" = 1 ]; then
		psql -X -q -v ON_ERROR_STOP=1 "$@"
	else
		PGPASSWORD="$PG_PASSWORD" psql -X -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" "$@"
	fi
}

start_pg() {
	mkdir -p "$RUN_DIR"
	local mode
	mode="$(pg_mode)"
	case "$mode" in
	external)
		log "using external Postgres (PGHOST=${PGHOST:-<default>})"
		;;
	native)
		local bin pgdata="$RUN_DIR/pgdata"
		bin="$(find_pg_bin)"
		if [ ! -f "$pgdata/PG_VERSION" ]; then
			log "initdb ($bin)"
			mkdir -p "$pgdata"
			printf '%s\n' "$PG_PASSWORD" >"$RUN_DIR/pwfile"
			chmod 600 "$RUN_DIR/pwfile"
			if [ "$(id -u)" -eq 0 ]; then chown -R postgres "$RUN_DIR"; fi
			as_pg_owner "$bin/initdb" -D "$pgdata" -U "$PG_USER" --pwfile="$RUN_DIR/pwfile" \
				--auth=scram-sha-256 -E UTF8 >"$RUN_DIR/initdb.log" 2>&1 || die "initdb failed, see $RUN_DIR/initdb.log"
			rm -f "$RUN_DIR/pwfile"
		fi
		if ! as_pg_owner "$bin/pg_ctl" -D "$pgdata" status >/dev/null 2>&1; then
			log "starting Postgres on 127.0.0.1:$PG_PORT"
			as_pg_owner "$bin/pg_ctl" -D "$pgdata" -l "$RUN_DIR/postgres.log" -w \
				-o "-p $PG_PORT -c listen_addresses=127.0.0.1 -c unix_socket_directories=''" start >/dev/null \
				|| die "Postgres did not start, see $RUN_DIR/postgres.log"
		else
			log "Postgres already running"
		fi
		;;
	docker)
		if ! docker ps --format '{{.Names}}' | grep -qx "$DOCKER_NAME"; then
			docker rm -f "$DOCKER_NAME" >/dev/null 2>&1 || true
			log "starting $DOCKER_IMAGE on 127.0.0.1:$PG_PORT"
			docker run -d --name "$DOCKER_NAME" -p "127.0.0.1:$PG_PORT:5432" \
				-e POSTGRES_USER="$PG_USER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB=postgres \
				"$DOCKER_IMAGE" >/dev/null
		fi
		local i
		for i in $(seq 1 60); do
			lpsql -d postgres -c 'select 1' >/dev/null 2>&1 && break
			[ "$i" -eq 60 ] && die "docker Postgres not ready after 60s"
			sleep 1
		done
		;;
	esac
	[ "$mode" = external ] || echo "$mode" >"$RUN_DIR/pg.mode"
}

recreate_db() {
	log "recreating database $PG_DB"
	lpsql -d postgres -c "drop database if exists \"$PG_DB\" with (force)"
	lpsql -d postgres -c "create database \"$PG_DB\""
	# Supabase roles that migrations GRANT to (same list as the IF-40 test replay).
	lpsql -d "$PG_DB" <<-'SQL'
		do $$
		declare r text;
		begin
		  foreach r in array array['anon', 'authenticated', 'service_role'] loop
		    if not exists (select 1 from pg_roles where rolname = r) then
		      execute format('create role %I nologin', r);
		    end if;
		  end loop;
		end $$;
	SQL
}

apply_migrations() {
	local f n=0
	for f in "$MIGRATIONS_DIR"/*.sql; do
		lpsql -d "$PG_DB" -f "$f" >/dev/null || die "migration failed: $(basename "$f")"
		n=$((n + 1))
	done
	[ "$n" -gt 0 ] || die "no migrations in $MIGRATIONS_DIR"
	log "applied $n migrations"
}

# Load one table from $DATA_DIR/<table>.json and/or <table>.part-*.json (each a JSON array of
# rows, or null / [] when empty — the output of scripts/export-prod-rows.sql).
load_table() {
	local table="$1" file found=0
	for file in "$DATA_DIR/$table.json" "$DATA_DIR/$table".part-*.json; do
		[ -s "$file" ] || continue
		found=1
		load_file "$table" "$file"
	done
	if [ "$found" -eq 0 ]; then log "  $table: no $table.json in $DATA_DIR, skipped"; fi
	log "  $table: $(lpsql -d "$PG_DB" -t -A -c "select count(*) from public.$table") rows"
}

load_file() {
	local table="$1" file="$2"
	# \set reads the file through psql (no argv size limit); the server only sees a literal.
	if lpsql -d "$PG_DB" <<-SQL
		\\set rows \`cat '$file'\`
		create temp table local_api_rows as select :'rows'::text as doc;
		do \$\$
		declare
		  cols text;
		  payload jsonb := (select nullif(btrim(doc), '')::jsonb from local_api_rows);
		begin
		  if payload is null or jsonb_typeof(payload) = 'null' then return; end if;
		  if jsonb_typeof(payload) <> 'array' then
		    raise exception '$table.json must be a JSON array of rows';
		  end if;
		  select string_agg(format('%I', column_name), ', ' order by ordinal_position) into cols
		    from information_schema.columns
		   where table_schema = 'public' and table_name = '$table' and is_generated = 'NEVER'
		     -- only exported keys, so columns missing from the JSON keep their defaults
		     and column_name in (select jsonb_object_keys(e) from jsonb_array_elements(payload) e);
		  if cols is null then return; end if;
		  -- FK triggers off while loading partial copies; identity values kept from prod.
		  perform set_config('session_replication_role', 'replica', true);
		  execute format(
		    'insert into public.%I (%s) overriding system value select %s from jsonb_populate_recordset(null::public.%I, \$1)',
		    '$table', cols, cols, '$table') using payload;
		end \$\$;
	SQL
	then :; else die "loading $(basename "$file") failed (must be a JSON array exported with scripts/export-prod-rows.sql)"; fi
}

reset_identities() {
	lpsql -d "$PG_DB" <<-'SQL'
		do $$
		declare r record; maxid bigint;
		begin
		  for r in select c.table_name, c.column_name, pg_get_serial_sequence(format('public.%I', c.table_name), c.column_name) seq
		             from information_schema.columns c
		            where c.table_schema = 'public' and c.is_identity = 'YES' loop
		    execute format('select max(%I) from public.%I', r.column_name, r.table_name) into maxid;
		    if maxid is not null then perform setval(r.seq, maxid); end if;
		  end loop;
		end $$;
	SQL
}

load_rows() {
	log "loading rows from $DATA_DIR"
	local t
	for t in "${TABLES[@]}"; do load_table "$t"; done
	reset_identities
}

backend_jar() {
	local f
	for f in "$ROOT"/backend/target/*.jar; do
		case "$f" in *-plain.jar) continue ;; esac
		if [ -f "$f" ]; then echo "$f"; return 0; fi
	done
	return 0
}

start_backend() {
	if [ -f "$RUN_DIR/backend.pid" ] && kill -0 "$(cat "$RUN_DIR/backend.pid")" 2>/dev/null; then
		log "stopping previous backend (pid $(cat "$RUN_DIR/backend.pid"))"
		kill "$(cat "$RUN_DIR/backend.pid")" 2>/dev/null || true
		sleep 2
	fi
	local jar
	jar="$(backend_jar)"
	if [ -z "$jar" ]; then
		log "building backend jar (./mvnw -q -DskipTests package)"
		(cd "$ROOT/backend" && ./mvnw -q -DskipTests package) || die "backend build failed"
		jar="$(backend_jar)"
		[ -n "$jar" ] || die "no jar in backend/target after the build"
	fi
	log "starting backend $(basename "$jar") on :$API_PORT"
	# Only local values; env -u keeps a prod DATABASE_* from the caller's shell out of the child.
	env -u DATABASE_URL -u DATABASE_USER -u DATABASE_PASSWORD -u SUPABASE_SERVICE_ROLE_KEY \
		DATABASE_URL="jdbc:postgresql://127.0.0.1:$PG_PORT/$PG_DB" \
		DATABASE_USER="$PG_USER" DATABASE_PASSWORD="$PG_PASSWORD" \
		SERVER_PORT="$API_PORT" \
		nohup java -jar "$jar" >"$RUN_DIR/backend.log" 2>&1 &
	echo $! >"$RUN_DIR/backend.pid"
	local i code
	for i in $(seq 1 "$HEALTH_TIMEOUT"); do
		code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$API_PORT/api/health" || true)"
		[ "$code" = 200 ] && break
		kill -0 "$(cat "$RUN_DIR/backend.pid")" 2>/dev/null || die "backend exited, see $RUN_DIR/backend.log"
		[ "$i" -eq "$HEALTH_TIMEOUT" ] && die "GET /api/health not 200 after ${HEALTH_TIMEOUT}s (last: $code), see $RUN_DIR/backend.log"
		sleep 1
	done
	log "API ready: http://localhost:$API_PORT  (GET /api/health = 200)"
	echo "http://localhost:$API_PORT"
}

stop_all() {
	if [ -f "$RUN_DIR/backend.pid" ]; then
		if kill "$(cat "$RUN_DIR/backend.pid")" 2>/dev/null; then log "backend stopped"; fi
		rm -f "$RUN_DIR/backend.pid"
	fi
	case "$( [ -f "$RUN_DIR/pg.mode" ] && cat "$RUN_DIR/pg.mode" || echo none)" in
	native)
		local bin
		if bin="$(find_pg_bin)" && as_pg_owner "$bin/pg_ctl" -D "$RUN_DIR/pgdata" -m fast stop >/dev/null 2>&1; then
			log "Postgres stopped"
		fi
		;;
	docker)
		if docker rm -f "$DOCKER_NAME" >/dev/null 2>&1; then log "Postgres container removed"; fi
		rm -f "$RUN_DIR/pg.mode"
		;;
	esac
}

main() {
	case "${1:-}" in
	--stop) stop_all; return ;;
	--db-only | "") ;;
	-h | --help) sed -n '2,22p' "$0"; return ;;
	*) die "unknown option $1 (use --stop, --db-only or --help)" ;;
	esac
	command -v psql >/dev/null || die "psql not found (install the PostgreSQL client)"
	start_pg
	recreate_db
	apply_migrations
	load_rows
	if [ "${1:-}" = --db-only ]; then
		log "database ready: $PG_DB (backend not started)"
		return
	fi
	start_backend
}

main "$@"
