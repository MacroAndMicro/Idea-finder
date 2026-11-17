package com.idea_finder.repo;

import org.springframework.jdbc.datasource.init.ScriptUtils;

/** Shared settings for tests that hit the Postgres from DATABASE_URL. */
public final class TestDb {

	/** Point Hibernate at the isolated if_test schema created by {@link #SCHEMA}. */
	public static final String ISOLATED_SCHEMA = "spring.jpa.properties.hibernate.default_schema=if_test";

	public static final String SCHEMA = "/db/opportunity_cards_test_schema.sql";

	public static final String DATA = "/db/opportunity_cards_test_data.sql";

	/** IF-24 fixture vectors for cards 1-5; requires pgvector (available in CI). */
	public static final String EMBEDDINGS = "/db/opportunity_cards_test_embeddings.sql";

	/** Run each script as a single statement (the schema script contains a DO $$ block). */
	public static final String WHOLE_FILE = ScriptUtils.EOF_STATEMENT_SEPARATOR;

	private TestDb() {
	}
}
