package com.idea_finder.repo;

import org.springframework.jdbc.datasource.init.ScriptUtils;

/** Shared settings for tests that hit the Postgres from DATABASE_URL. */
public final class TestDb {

	/** Point Hibernate at the isolated if_test schema built from supabase/migrations by {@link MigratedTestSchema}. */
	public static final String ISOLATED_SCHEMA = "spring.jpa.properties.hibernate.default_schema=if_test";

	/** Empties every if_test table (the schema itself comes from supabase/migrations, IF-40). */
	public static final String SCHEMA = "/db/reset_test_schema.sql";

	public static final String DATA = "/db/opportunity_cards_test_data.sql";

	/** IF-24 fixture vectors for cards 1-5 (pgvector is required by the migrations). */
	public static final String EMBEDDINGS = "/db/opportunity_cards_test_embeddings.sql";

	/** Run each script as a single statement (the reset script is a DO $$ block). */
	public static final String WHOLE_FILE = ScriptUtils.EOF_STATEMENT_SEPARATOR;

	private TestDb() {
	}
}
