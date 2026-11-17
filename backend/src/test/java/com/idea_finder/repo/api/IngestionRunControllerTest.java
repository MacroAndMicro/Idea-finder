package com.idea_finder.repo.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.TestDb;

/**
 * IF-36: GET /api/ingestion-runs on the seeded if_test schema. Fixture runs, newest first:
 * 3 hackernews Failed (no finished_at), 2 github Partial, 1 github Success.
 */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class IngestionRunControllerTest {

	@Autowired
	MockMvc mvc;

	@Test
	void newestStartedFirstWithAllFields() throws Exception {
		mvc.perform(get("/api/ingestion-runs"))
			.andExpect(status().isOk())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
			.andExpect(jsonPath("$.items[*].id").value(contains(3, 2, 1)))
			.andExpect(jsonPath("$.page").value(0))
			.andExpect(jsonPath("$.size").value(20))
			.andExpect(jsonPath("$.total_elements").value(3))
			.andExpect(jsonPath("$.items[1].keys()").value(contains("id", "source_platform", "started_at",
				"finished_at", "status", "fetched_count", "inserted_count", "skipped_count", "error_summary")))
			.andExpect(jsonPath("$.items[1].source_platform").value("github"))
			.andExpect(jsonPath("$.items[1].started_at").value("2026-11-16T00:00:00Z"))
			.andExpect(jsonPath("$.items[1].finished_at").value("2026-11-16T00:02:00Z"))
			.andExpect(jsonPath("$.items[1].status").value("Partial"))
			.andExpect(jsonPath("$.items[1].fetched_count").value(4))
			.andExpect(jsonPath("$.items[1].inserted_count").value(3))
			.andExpect(jsonPath("$.items[1].skipped_count").value(1))
			.andExpect(jsonPath("$.items[1].error_summary").value("secret-ish error detail"))
			.andExpect(jsonPath("$.items[0].finished_at").doesNotExist())
			.andExpect(jsonPath("$.items[2].error_summary").doesNotExist());
	}

	@Test
	void filterBySource() throws Exception {
		mvc.perform(get("/api/ingestion-runs").param("source", "GitHub"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(2, 1)));
	}

	@Test
	void filterByStatusCaseInsensitive() throws Exception {
		mvc.perform(get("/api/ingestion-runs").param("status", "failed"))
			.andExpect(jsonPath("$.items[*].id").value(contains(3)));
	}

	@Test
	void filtersCombine() throws Exception {
		mvc.perform(get("/api/ingestion-runs").param("source", "github").param("status", "Success"))
			.andExpect(jsonPath("$.items[*].id").value(contains(1)));
		mvc.perform(get("/api/ingestion-runs").param("source", "reddit"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items").isEmpty())
			.andExpect(jsonPath("$.total_elements").value(0));
	}

	@Test
	void paging() throws Exception {
		mvc.perform(get("/api/ingestion-runs").param("size", "2").param("page", "1"))
			.andExpect(jsonPath("$.items[*].id").value(contains(1)))
			.andExpect(jsonPath("$.total_pages").value(2));
		mvc.perform(get("/api/ingestion-runs").param("size", "100"))
			.andExpect(status().isOk());
	}

	@ParameterizedTest
	@CsvSource({
		"source, twitter", "status, Running", "status, success'--", "size, 0", "size, 101", "page, -1"
	})
	void invalidParamsAre400ProblemDetail(String param, String value) throws Exception {
		mvc.perform(get("/api/ingestion-runs").param(param, value))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.parameter").value(param));
	}

	@Test
	void nonNumericSizeIs400() throws Exception {
		mvc.perform(get("/api/ingestion-runs").param("size", "lots"))
			.andExpect(status().isBadRequest());
	}

	@Test
	void writesAreDenied() throws Exception {
		mvc.perform(post("/api/ingestion-runs").contentType("application/json").content("{}"))
			.andExpect(status().isForbidden());
		mvc.perform(put("/api/ingestion-runs").contentType("application/json").content("{}"))
			.andExpect(status().isForbidden());
		mvc.perform(delete("/api/ingestion-runs")).andExpect(status().isForbidden());
		mvc.perform(get("/api/ingestion-runs/1")).andExpect(status().isForbidden());
	}

	@Test
	void longErrorSummaryIsTruncated() {
		String longText = "x".repeat(IngestionRunResponse.MAX_ERROR_SUMMARY + 50);
		assertThat(IngestionRunResponse.truncate(longText))
			.hasSize(IngestionRunResponse.MAX_ERROR_SUMMARY + 1)
			.endsWith("…");
		assertThat(IngestionRunResponse.truncate("short")).isEqualTo("short");
		assertThat(IngestionRunResponse.truncate(null)).isNull();
	}
}
