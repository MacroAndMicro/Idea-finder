# Running the API locally against prod rows

The routine sandbox cannot open a raw TCP connection to Supabase, so QA and the User Simulator
run the backend locally against a **copy** of prod rows (founder decision on IF-46, option D).
`scripts/local-api-from-prod.sh` does it in one command. It never connects to prod and never
needs `SUPABASE_SERVICE_ROLE_KEY` or a prod `DATABASE_URL`: it uses local throwaway
credentials only.

## 1. Export the rows (Supabase connector, read-only)

Run each statement in [`scripts/export-prod-rows.sql`](../scripts/export-prod-rows.sql) with
the Supabase connector (`execute_sql`). Each returns one row whose `rows` column is a JSON
array. Save that array, unchanged, as:

| Table | File |
|---|---|
| `opportunity_cards` | `.local-data/opportunity_cards.json` |
| `raw_signals` | `.local-data/raw_signals.json` |
| `ingestion_runs` | `.local-data/ingestion_runs.json` |
| `signal_extractions` | `.local-data/signal_extractions.json` |
| `card_signals` | `.local-data/card_signals.json` |

`.local-data/` is gitignored — never commit it. A missing file or an empty array (`[]`) just
means that table stays empty. For a large table, export it in chunks (`where id > N ... limit 500`
inside the subquery) and save them as `<table>.part-001.json`, `<table>.part-002.json`, …; every
part is loaded. Only columns present in the JSON are inserted, so the export must use `select *`.

## 2. Start

```bash
scripts/local-api-from-prod.sh            # Postgres + migrations + rows + backend on :8080
scripts/local-api-from-prod.sh --db-only  # same, without the backend
scripts/local-api-from-prod.sh --stop     # stop the backend and Postgres
```

What it does, every time (idempotent — re-running reloads the current files):

1. Starts Postgres with pgvector on `127.0.0.1:54329`: local PostgreSQL 16+ binaries with the
   `vector` extension (`apt-get install postgresql-16-pgvector`; as root it runs Postgres as the
   `postgres` OS user), or else Docker `pgvector/pgvector:pg16`. Data lives in `.local-data/run/`.
2. Drops and recreates the `idea_finder_local` database, creates the Supabase roles
   (`anon`, `authenticated`, `service_role`) and applies `supabase/migrations/*.sql` in filename
   order (the same replay the IF-40 tests use, but into `public`).
3. Loads the JSON files with FK checks off (partial copies are fine) and keeps prod ids; identity
   sequences continue after the highest loaded id.
4. Builds the backend jar (`./mvnw -q -DskipTests package`) if `backend/target` has none, starts it
   on `:8080` with only the local `DATABASE_*` values (prod `DATABASE_*` and
   `SUPABASE_SERVICE_ROLE_KEY` are removed from its environment), waits for
   `GET /api/health` = 200 and prints the base URL.

Logs: `.local-data/run/backend.log`, `.local-data/run/postgres.log`.
Rebuild the jar after backend changes: `rm backend/target/*.jar` (or `./mvnw package`) and re-run.

| Variable | Default | Meaning |
|---|---|---|
| `LOCAL_DATA_DIR` | `.local-data` | Where the exported JSON files are |
| `LOCAL_PG_PORT` | `54329` | Local Postgres port |
| `LOCAL_PG_DB` | `idea_finder_local` | Database that is recreated on each start |
| `LOCAL_API_PORT` | `8080` | Backend port |
| `LOCAL_API_HEALTH_TIMEOUT` | `120` | Seconds to wait for `/api/health` |
| `LOCAL_PG_EXTERNAL` | `0` | `1` = use an already running server from `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD` (the CI smoke test does this) |

## 3. Use it

```bash
curl -s http://localhost:8080/api/health
curl -s http://localhost:8080/api/stats
curl -s 'http://localhost:8080/api/cards?size=5'
```

Endpoints: [`docs/api.md`](api.md).

**Empty prod (0 cards today):** the API still starts; `/api/cards` returns
`{"items": [], "total_elements": 0, ...}` and `/api/stats` shows the signal and ingestion-run
counts. That is the correct result, not a script failure — report "0 cards in prod" rather than
inventing data. To exercise card pages anyway, use the backend test fixtures, never fabricated
rows presented as prod data.

## Test

`backend/src/test/java/com/idea_finder/repo/LocalApiScriptTest.java` runs `--db-only` against the
CI Postgres (in a throwaway `if_local_api_smoke` database, only when `DATABASE_URL` is localhost)
and checks the migration replay, the JSON load (incl. a 1536-dim embedding and `.part-*` files)
and identity continuation. `shellcheck scripts/local-api-from-prod.sh` is clean.
