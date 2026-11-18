package com.idea_finder.repo.api;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * IF-66: cheap liveness check of the database ({@code select 1} with a short query timeout).
 * Never throws; a failure is logged once per call (the log line carries the request id via the MDC).
 */
@Component
public class DatabaseHealthProbe {

	private static final Logger log = LoggerFactory.getLogger(DatabaseHealthProbe.class);

	private final JdbcTemplate jdbc;

	public DatabaseHealthProbe(DataSource dataSource,
			@Value("${app.health.db-timeout-seconds:2}") int timeoutSeconds) {
		// Own template so the query timeout does not leak into the shared JdbcTemplate.
		this.jdbc = new JdbcTemplate(dataSource);
		this.jdbc.setQueryTimeout(Math.max(1, timeoutSeconds));
	}

	/** True when {@code select 1} returns 1. */
	public boolean isUp() {
		try {
			Integer one = jdbc.queryForObject("select 1", Integer.class);
			return one != null && one == 1;
		}
		catch (RuntimeException ex) {
			// Class name only: the message can carry hostnames or credentials hints.
			log.warn("Health check: database unreachable ({})", ex.getClass().getSimpleName());
			return false;
		}
	}
}
