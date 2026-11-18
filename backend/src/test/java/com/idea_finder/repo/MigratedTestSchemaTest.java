package com.idea_finder.repo;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

/** IF-40: the if_test schema is built by replaying supabase/migrations on an empty schema. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
class MigratedTestSchemaTest {

	@Autowired
	JdbcTemplate jdbc;

	@Test
	void replayYieldsTheSameElevenTablesAsProd() {
		List<String> tables = jdbc.queryForList(
			"select tablename from pg_tables where schemaname = 'if_test' order by tablename", String.class);
		assertThat(tables).containsExactly("agent_inbox", "agent_run_reports", "card_signals", "ingestion_runs",
			"opportunity_cards", "project_board", "raw_signals", "signal_extractions", "system_prompts",
			"system_prompts_history", "test_personas");
	}

	@Test
	void columnsAddedByLaterMigrationsArePresent() {
		List<String> cols = jdbc.queryForList("""
			select table_name || '.' || column_name from information_schema.columns
			where table_schema = 'if_test' and (table_name, column_name) in (
			  ('opportunity_cards', 'embedding'), ('opportunity_cards', 'last_seen_at'),
			  ('project_board', 'ticket_key'), ('raw_signals', 'embedding'))
			order by 1""", String.class);
		assertThat(cols).containsExactly("opportunity_cards.embedding", "opportunity_cards.last_seen_at",
			"project_board.ticket_key", "raw_signals.embedding");
	}

	@Test
	void rlsIsEnabledOnEveryTable() {
		Integer withoutRls = jdbc.queryForObject("""
			select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
			where n.nspname = 'if_test' and c.relkind = 'r' and not c.relrowsecurity""", Integer.class);
		assertThat(withoutRls).isZero();
	}

	@Test
	void nothingIsLeftQualifiedWithPublic() {
		assertThat(MigratedTestSchema.rewrite("alter table public.raw_signals add x; grant usage on all sequences in schema public to r;"))
			.isEqualTo("alter table if_test.raw_signals add x; grant usage on all sequences in schema if_test to r;");
		assertThat(MigratedTestSchema.rewrite("create extension if not exists vector with schema public;"))
			.isEqualTo("create extension if not exists vector with schema public;");
	}
}
