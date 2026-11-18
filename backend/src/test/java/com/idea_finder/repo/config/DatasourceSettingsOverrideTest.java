package com.idea_finder.repo.config;

import static org.assertj.core.api.Assertions.assertThat;

import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import com.zaxxer.hikari.HikariDataSource;

/** IF-52: every pool setting can be overridden by its environment variable. */
@SpringBootTest(properties = {"DB_POOL_MAX_SIZE=3", "DB_POOL_MIN_IDLE=0", "DB_CONNECTION_TIMEOUT_MS=4000",
	"DB_IDLE_TIMEOUT_MS=60000", "DB_MAX_LIFETIME_MS=120000", "DB_PREPARE_THRESHOLD=5"})
class DatasourceSettingsOverrideTest {

	@Autowired
	DataSource dataSource;

	@Test
	void environmentVariablesOverrideDefaults() {
		HikariDataSource ds = (HikariDataSource) dataSource;
		assertThat(ds.getMaximumPoolSize()).isEqualTo(3);
		assertThat(ds.getMinimumIdle()).isZero();
		assertThat(ds.getConnectionTimeout()).isEqualTo(4_000);
		assertThat(ds.getIdleTimeout()).isEqualTo(60_000);
		assertThat(ds.getMaxLifetime()).isEqualTo(120_000);
		assertThat(ds.getDataSourceProperties().getProperty("prepareThreshold")).isEqualTo("5");
	}
}
