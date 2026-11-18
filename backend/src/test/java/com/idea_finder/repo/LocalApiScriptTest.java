package com.idea_finder.repo;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * IF-84 smoke test for {@code scripts/local-api-from-prod.sh}: runs its {@code --db-only} part
 * (migration replay + JSON row load) against the test Postgres from DATABASE_URL, in a separate
 * throwaway database. No network to prod. Skipped unless DATABASE_URL points at localhost, so it
 * can never create a database on a remote server.
 */
class LocalApiScriptTest {

	private static final String SMOKE_DB = "if_local_api_smoke";

	private static String host;

	private static int port;

	private static String user;

	private static String password;

	@TempDir
	static Path dataDir;

	@BeforeAll
	static void requireLocalPostgres() {
		String url = System.getenv("DATABASE_URL");
		assumeTrue(url != null && url.startsWith("jdbc:postgresql://"), "DATABASE_URL not set");
		URI uri = URI.create(url.substring("jdbc:".length()));
		host = uri.getHost();
		port = uri.getPort() == -1 ? 5432 : uri.getPort();
		assumeTrue("localhost".equals(host) || "127.0.0.1".equals(host), "DATABASE_URL is not local");
		user = System.getenv("DATABASE_USER");
		password = System.getenv("DATABASE_PASSWORD");
		assumeTrue(onPath("psql"), "psql not on PATH");
	}

	@AfterAll
	static void dropSmokeDatabase() throws SQLException {
		if (host == null) {
			return;
		}
		try (Connection c = connect("postgres"); Statement s = c.createStatement()) {
			s.execute("drop database if exists " + SMOKE_DB + " with (force)");
		}
	}

	@Test
	void replaysMigrationsAndLoadsExportedRows() throws Exception {
		String embedding = "[" + String.join(",", Collections.nCopies(1536, "0.01")) + "]";
		write("opportunity_cards.json", """
			[{"id": 7, "title": "Fixture card", "source_platform": "github",
			  "source_url": "https://github.com/o/r/issues/7", "problem_statement": "P",
			  "trigger_context": "T", "economic_intent": "High", "confidence_score": 80,
			  "embedding": "%s", "embedding_model": "m",
			  "created_at": "2026-11-10T00:00:00+00:00", "updated_at": "2026-11-10T00:00:00+00:00"}]
			""".formatted(embedding));
		write("ingestion_runs.json", """
			[{"id": 16, "source_platform": "github", "started_at": "2026-11-18T19:18:24+00:00",
			  "status": "Success", "fetched_count": 0, "inserted_count": 0, "skipped_count": 0}]
			""");
		write("ingestion_runs.part-001.json", """
			[{"id": 17, "source_platform": "hackernews", "started_at": "2026-11-18T19:18:39+00:00",
			  "status": "Success", "fetched_count": 13, "inserted_count": 4, "skipped_count": 9}]
			""");
		write("card_signals.json", "[]"); // json_agg over an empty table gives null / []

		ProcessBuilder builder = new ProcessBuilder("bash", script().toString(), "--db-only")
			.redirectErrorStream(true)
			.directory(script().getParent().toFile());
		env(builder);
		Process process = builder.start();
		String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
		assertThat(process.waitFor(120, TimeUnit.SECONDS)).isTrue();
		assertThat(process.exitValue()).as(output).isZero();
		assertThat(output).contains("applied", "opportunity_cards: 1 rows", "ingestion_runs: 2 rows",
				"raw_signals: 0 rows", "database ready");

		try (Connection c = connect(SMOKE_DB); Statement s = c.createStatement()) {
			assertThat(single(s, "select vector_dims(embedding) from public.opportunity_cards where id = 7"))
				.isEqualTo(1536);
			assertThat(single(s, "select count(*) from public.ingestion_runs")).isEqualTo(2);
			// identities continue after the loaded prod ids
			assertThat(single(s, """
					insert into public.ingestion_runs (source_platform, status) values ('github', 'Success')
					returning id""")).isEqualTo(18);
			// every migration file was applied: the newest table exists
			assertThat(single(s, "select count(*) from public.synthesis_rejections")).isZero();
		}
	}

	private static long single(Statement s, String sql) throws SQLException {
		try (ResultSet rs = s.executeQuery(sql)) {
			assertThat(rs.next()).isTrue();
			return rs.getLong(1);
		}
	}

	private static void env(ProcessBuilder pb) {
		Map<String, String> env = pb.environment();
			env.put("LOCAL_PG_EXTERNAL", "1");
			env.put("LOCAL_PG_DB", SMOKE_DB);
			env.put("LOCAL_DATA_DIR", dataDir.toString());
			env.put("PGHOST", host);
			env.put("PGPORT", Integer.toString(port));
			if (user != null) {
				env.put("PGUSER", user);
			}
			if (password != null) {
				env.put("PGPASSWORD", password);
			}
	}

	private static void write(String name, String json) throws IOException {
		Files.writeString(dataDir.resolve(name), json, StandardCharsets.UTF_8);
	}

	private static Connection connect(String database) throws SQLException {
		return DriverManager.getConnection("jdbc:postgresql://" + host + ":" + port + "/" + database, user, password);
	}

	private static Path script() {
		return MigratedTestSchema.migrationsDir().getParent().getParent().resolve("scripts/local-api-from-prod.sh");
	}

	private static boolean onPath(String command) {
		String path = System.getenv("PATH");
		return path != null && List.of(path.split(java.io.File.pathSeparator))
			.stream()
			.anyMatch(dir -> Files.isExecutable(Path.of(dir, command)));
	}
}
