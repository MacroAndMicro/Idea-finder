package com.idea_finder.repo.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;

import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.postgresql.PGConnection;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;

import com.zaxxer.hikari.HikariDataSource;

/** IF-52: effective datasource and server defaults for the Supabase transaction pooler. */
@SpringBootTest
class DatasourceSettingsTest {

	@Autowired
	DataSource dataSource;

	@Autowired
	Environment env;

	@Test
	void poolerSafeDefaults() {
		assertThat(dataSource).isInstanceOf(HikariDataSource.class);
		HikariDataSource ds = (HikariDataSource) dataSource;
		assertThat(ds.getDataSourceProperties().getProperty("prepareThreshold")).isEqualTo("0");
		assertThat(ds.getMaximumPoolSize()).isEqualTo(5);
		assertThat(ds.getMinimumIdle()).isEqualTo(1);
		assertThat(ds.getConnectionTimeout()).isEqualTo(10_000);
		assertThat(ds.getIdleTimeout()).isEqualTo(300_000);
		assertThat(ds.getMaxLifetime()).isEqualTo(900_000);
	}

	@Test
	void preparedStatementsAreOffOnARealConnection() throws Exception {
		try (Connection connection = dataSource.getConnection()) {
			assertThat(connection.unwrap(PGConnection.class).getPrepareThreshold()).isZero();
		}
	}

	@Test
	void errorsNeverIncludeInternalsAndShutdownIsGraceful() {
		assertThat(env.getProperty("server.error.include-stacktrace")).isEqualTo("never");
		assertThat(env.getProperty("server.error.include-message")).isEqualTo("never");
		assertThat(env.getProperty("server.error.include-binding-errors")).isEqualTo("never");
		assertThat(env.getProperty("server.error.include-exception")).isEqualTo("false");
		assertThat(env.getProperty("server.shutdown")).isEqualTo("graceful");
		assertThat(env.getProperty("spring.lifecycle.timeout-per-shutdown-phase")).isEqualTo("20s");
	}
}
