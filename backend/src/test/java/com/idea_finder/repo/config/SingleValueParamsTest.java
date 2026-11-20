package com.idea_finder.repo.config;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
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

/** IF-92: a repeated query parameter is a 400 ProblemDetail naming it, on every API endpoint with params. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class SingleValueParamsTest {

	@Autowired
	MockMvc mvc;

	@ParameterizedTest
	@CsvSource({
		"/api/cards, source, reddit, github",
		"/api/cards, page, 0, 5",
		"/api/cards, q, csv, export",
		"/api/cards/facets, intent, High, Low",
		"/api/cards/1/similar, limit, 3, 5",
		"/api/cards/1/signals, size, 5, 10",
		"/api/ingestion-runs, status, success, failed",
		"/api/ingestion-runs, page, 0, 0",
	})
	void repeatedParamIs400NamingIt(String path, String param, String first, String second) throws Exception {
		mvc.perform(get(path).param(param, first, second))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(header().exists(RequestIdFilter.HEADER))
			.andExpect(jsonPath("$.title").value("Invalid request parameter"))
			.andExpect(jsonPath("$.parameter").value(param))
			.andExpect(jsonPath("$.detail").value(param + " must be given at most once"));
	}

	@Test
	void singleValidParamsStill200() throws Exception {
		mvc.perform(get("/api/cards").param("source", "reddit").param("page", "0"))
			.andExpect(status().isOk());
		mvc.perform(get("/api/ingestion-runs").param("page", "0"))
			.andExpect(status().isOk());
	}

	@Test
	void paramlessEndpointsUnaffected() throws Exception {
		mvc.perform(get("/api/stats").param("x", "1", "2")).andExpect(status().isOk());
	}
}
