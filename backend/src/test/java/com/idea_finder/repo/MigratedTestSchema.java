package com.idea_finder.repo;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import javax.sql.DataSource;

import org.springframework.context.ApplicationContext;
import org.springframework.core.Ordered;
import org.springframework.test.context.TestContext;
import org.springframework.test.context.TestExecutionListener;

/**
 * IF-40: builds the isolated {@code if_test} schema from {@code supabase/migrations/*.sql}
 * (filename order), once per JVM, before the first test class that has a DataSource.
 * Each migration's {@code public.} references are rewritten to {@code if_test.}, so tests can
 * never touch public tables even when DATABASE_URL points at a real database.
 * Per-test isolation stays with {@link TestDb#SCHEMA} (truncate) inside the rolled-back test transaction.
 * Registered for every test class through {@code META-INF/spring.factories}.
 */
public class MigratedTestSchema implements TestExecutionListener, Ordered {

	static final String SCHEMA = "if_test";

	private static final Pattern PUBLIC_QUALIFIER = Pattern.compile("(?<![\\w.\"])public\\.");

	private static final Pattern IN_SCHEMA_PUBLIC = Pattern.compile("(?i)in schema public\\b");

	/** Supabase roles that migrations GRANT to; created when missing (plain Postgres in CI). */
	private static final String ROLES = """
		do $$
		declare r text;
		begin
		  foreach r in array array['anon', 'authenticated', 'service_role'] loop
		    if not exists (select 1 from pg_roles where rolname = r) then
		      execute format('create role %I nologin', r);
		    end if;
		  end loop;
		end $$""";

	private static volatile boolean built;

	@Override
	public int getOrder() {
		return Ordered.HIGHEST_PRECEDENCE;
	}

	@Override
	public void beforeTestClass(TestContext testContext) {
		if (built) {
			return;
		}
		ApplicationContext context = testContext.getApplicationContext();
		if (context.getBeanNamesForType(DataSource.class).length == 0) {
			return;
		}
		build(context.getBean(DataSource.class));
	}

	static synchronized void build(DataSource dataSource) {
		if (built) {
			return;
		}
		try (Connection connection = dataSource.getConnection(); Statement statement = connection.createStatement()) {
			boolean autoCommit = connection.getAutoCommit();
			connection.setAutoCommit(true);
			try {
				statement.execute(ROLES);
				statement.execute("drop schema if exists " + SCHEMA + " cascade");
				statement.execute("create schema " + SCHEMA);
				for (Path file : migrationFiles()) {
					try {
						statement.execute(rewrite(Files.readString(file, StandardCharsets.UTF_8)));
					}
					catch (SQLException e) {
						throw new IllegalStateException("Migration failed in " + SCHEMA + ": " + file.getFileName(), e);
					}
					catch (IOException e) {
						throw new UncheckedIOException(e);
					}
				}
			}
			finally {
				connection.setAutoCommit(autoCommit);
			}
		}
		catch (SQLException e) {
			throw new IllegalStateException("Could not build the " + SCHEMA + " schema from supabase/migrations", e);
		}
		built = true;
	}

	/** Point every schema-qualified object at if_test instead of public. */
	static String rewrite(String sql) {
		String out = PUBLIC_QUALIFIER.matcher(sql).replaceAll(SCHEMA + ".");
		return IN_SCHEMA_PUBLIC.matcher(out).replaceAll("in schema " + SCHEMA);
	}

	/** All supabase/migrations/*.sql files, sorted by filename (= timestamp order). */
	static List<Path> migrationFiles() {
		Path dir = migrationsDir();
		try (Stream<Path> files = Files.list(dir)) {
			List<Path> sorted = files
				.filter(p -> p.getFileName().toString().endsWith(".sql"))
				.sorted((a, b) -> a.getFileName().toString().compareTo(b.getFileName().toString()))
				.toList();
			if (sorted.isEmpty()) {
				throw new IllegalStateException("No migrations found in " + dir);
			}
			return sorted;
		}
		catch (IOException e) {
			throw new UncheckedIOException(e);
		}
	}

	/** supabase/migrations, searched upwards from the working directory (backend/ under Maven). */
	static Path migrationsDir() {
		Path dir = Path.of("").toAbsolutePath();
		while (dir != null) {
			Path candidate = dir.resolve("supabase").resolve("migrations");
			if (Files.isDirectory(candidate)) {
				return candidate;
			}
			dir = dir.getParent();
		}
		throw new IllegalStateException("supabase/migrations not found above " + Path.of("").toAbsolutePath());
	}
}
