package com.idea_finder.repo.api;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasKey;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.TestDb;

/** Full stack (security + MVC + JPA) against the Postgres from DATABASE_URL. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardControllerTest {

	@Autowired
	MockMvc mvc;

	@Test
	void listDefaultsSortByConfidenceThenNewestWithUnscoredLast() throws Exception {
		mvc.perform(get("/api/cards"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(1, 2, 6, 3, 4, 5)))
			.andExpect(jsonPath("$.page").value(0))
			.andExpect(jsonPath("$.size").value(20))
			.andExpect(jsonPath("$.total_elements").value(6))
			.andExpect(jsonPath("$.total_pages").value(1));
	}

	@Test
	void sortNewest() throws Exception {
		mvc.perform(get("/api/cards").param("sort", "newest"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(5, 4, 3, 2, 1, 6)));
	}

	@Test
	void responseShapeHasAllCardFieldsAndNoEmbedding() throws Exception {
		mvc.perform(get("/api/cards/1"))
			.andExpect(status().isOk())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
			.andExpect(jsonPath("$.id").value(1))
			.andExpect(jsonPath("$.title").value("CI flaky test triage"))
			.andExpect(jsonPath("$.problem_statement").value("P1"))
			.andExpect(jsonPath("$.trigger_context").value("T1"))
			.andExpect(jsonPath("$.market_size").value("M1"))
			.andExpect(jsonPath("$.duct_tape_solutions").value("D1"))
			.andExpect(jsonPath("$.economic_intent").value("High"))
			.andExpect(jsonPath("$.mvp_wedge").value("W1"))
			.andExpect(jsonPath("$.confidence_score").value(90))
			.andExpect(jsonPath("$.source_platform").value("github"))
			.andExpect(jsonPath("$.source_url").value("https://github.com/o/r/issues/1"))
			.andExpect(jsonPath("$.raw_content_snippet").value("snippet 1"))
			.andExpect(jsonPath("$.created_at").exists())
			.andExpect(jsonPath("$", not(hasKey("embedding"))))
			.andExpect(jsonPath("$", not(hasKey("embedding_model"))));
	}

	@Test
	void filtersCombine() throws Exception {
		mvc.perform(get("/api/cards").param("source", "github").param("minConfidence", "50").param("intent", "high"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(1)))
			.andExpect(jsonPath("$.total_elements").value(1));
	}

	@Test
	void filterByMinConfidence() throws Exception {
		mvc.perform(get("/api/cards").param("minConfidence", "70"))
			.andExpect(jsonPath("$.items[*].id").value(contains(1, 2, 6)));
	}

	@Test
	void paging() throws Exception {
		mvc.perform(get("/api/cards").param("page", "1").param("size", "4"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(4, 5)))
			.andExpect(jsonPath("$.page").value(1))
			.andExpect(jsonPath("$.size").value(4))
			.andExpect(jsonPath("$.total_pages").value(2));
	}

	@Test
	void sizeFiftyIsAllowed() throws Exception {
		mvc.perform(get("/api/cards").param("size", "50")).andExpect(status().isOk());
	}

	@ParameterizedTest
	@CsvSource({
		"size, 51", "size, 0", "page, -1", "page, 10001",
		"minConfidence, 101", "minConfidence, -1",
		"source, twitter", "intent, huge", "sort, oldest"
	})
	void invalidParamsReturn400ProblemDetail(String name, String value) throws Exception {
		mvc.perform(get("/api/cards").param(name, value))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(400))
			.andExpect(jsonPath("$.parameter").value(name));
	}

	@ParameterizedTest
	@CsvSource({"size, abc", "page, 1.5", "minConfidence, high", "minConfidence, NaN",
		"minConfidence, Infinity", "minConfidence, -Infinity"})
	void malformedParamsReturn400ProblemDetail(String name, String value) throws Exception {
		mvc.perform(get("/api/cards").param(name, value))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(400))
			.andExpect(jsonPath("$.title").value("Invalid request parameter"))
			.andExpect(jsonPath("$.parameter").value(name))
			.andExpect(jsonPath("$.detail", not(containsString("Failed to convert"))));
	}

	/** IF-95: type-mismatch 400s name the parameter and the expected type, like other validation errors. */
	@Test
	void nanMinConfidenceNamesExpectedRange() throws Exception {
		mvc.perform(get("/api/cards").param("minConfidence", "NaN"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.detail").value("minConfidence must be a number between 0 and 100"));
		mvc.perform(get("/api/cards/facets").param("minConfidence", "NaN"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.parameter").value("minConfidence"));
	}

	@ParameterizedTest
	@ValueSource(strings = {"/api/cards/abc", "/api/cards/99999999999999999999", "/api/cards/export",
		"/api/cards/abc/similar", "/api/cards/abc/signals"})
	void malformedIdReturns400WithParameter(String path) throws Exception {
		mvc.perform(get(path).param("format", "csv"))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(400))
			.andExpect(jsonPath("$.title").value("Invalid request parameter"))
			.andExpect(jsonPath("$.parameter").value("id"))
			.andExpect(jsonPath("$.detail").value("id must be a positive integer"))
			.andExpect(jsonPath("$.detail", not(containsString("abc"))))
			.andExpect(jsonPath("$.detail", not(containsString("99999"))));
	}

	@Test
	void unknownIdReturns404ProblemDetail() throws Exception {
		mvc.perform(get("/api/cards/999"))
			.andExpect(status().isNotFound())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(404))
			.andExpect(jsonPath("$.detail").value("Card 999 not found"));
	}

	@Test
	void nonNumericIdReturns400() throws Exception {
		mvc.perform(get("/api/cards/abc"))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON));
	}

	@Test
	void sqlInjectionAttemptIsJustAnInvalidValue() throws Exception {
		mvc.perform(get("/api/cards").param("source", "github' or '1'='1"))
			.andExpect(status().isBadRequest());
	}
}
