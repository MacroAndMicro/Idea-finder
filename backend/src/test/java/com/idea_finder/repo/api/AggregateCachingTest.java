package com.idea_finder.repo.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.hamcrest.Matchers.anyOf;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Duration;

import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.TestDb;

/** IF-68: Cache-Control only on successful /api/stats and /api/cards/facets responses. */
class AggregateCachingTest {

	@Nested
	@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
	@AutoConfigureMockMvc
	@Transactional
	@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
	class Defaults {

		@Autowired
		MockMvc mvc;

		@ParameterizedTest
		@ValueSource(strings = {"/api/stats", "/api/cards/facets", "/api/cards/facets?source=github"})
		void aggregatesArePubliclyCacheable(String url) throws Exception {
			mvc.perform(get(url))
				.andExpect(status().isOk())
				.andExpect(header().string("Cache-Control", "max-age=60, public"))
				.andExpect(header().doesNotExist("Pragma"));
		}

		@ParameterizedTest
		@ValueSource(strings = {"/api/cards", "/api/cards/1", "/api/cards/1/signals", "/api/cards/1/similar",
			"/api/ingestion-runs"})
		void otherEndpointsStayUncached(String url) throws Exception {
			mvc.perform(get(url))
				.andExpect(status().isOk())
				.andExpect(header().string("Cache-Control", anyOf(nullValue(), not(containsString("public")))));
		}

		@Test
		void errorsAreNotCacheable() throws Exception {
			mvc.perform(get("/api/cards/facets").param("minConfidence", "abc"))
				.andExpect(status().isBadRequest())
				.andExpect(header().string("Cache-Control", containsString("no-store")));
			mvc.perform(get("/api/cards/999999"))
				.andExpect(status().isNotFound())
				.andExpect(header().string("Cache-Control", containsString("no-store")));
		}
	}

	@Nested
	@SpringBootTest(properties = {TestDb.ISOLATED_SCHEMA, "app.cache.aggregate-max-age=5m"})
	@AutoConfigureMockMvc
	@Transactional
	@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
	class Configured {

		@Autowired
		MockMvc mvc;

		@Test
		void maxAgeComesFromConfig() throws Exception {
			mvc.perform(get("/api/stats")).andExpect(header().string("Cache-Control", "max-age=300, public"));
		}
	}

	@Nested
	class Unit {

		@Test
		void zeroDisablesHeader() {
			assertThat(new AggregateCaching(Duration.ZERO).ok("x").getHeaders().getCacheControl()).isNull();
		}

		@Test
		void negativeRejected() {
			assertThatThrownBy(() -> new AggregateCaching(Duration.ofSeconds(-1)))
				.isInstanceOf(IllegalArgumentException.class);
		}
	}
}
