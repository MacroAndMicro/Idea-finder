package com.idea_finder.repo.api;

import static org.hamcrest.Matchers.contains;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
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

/** IF-17: keyword search (q) on GET /api/cards. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardSearchTest {

	@Autowired
	MockMvc mvc;

	@Test
	void matchesTitleCaseInsensitively() throws Exception {
		mvc.perform(get("/api/cards").param("q", "INVOIC"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(3)))
			.andExpect(jsonPath("$.total_elements").value(1));
	}

	@Test
	void matchesProblemStatement() throws Exception {
		mvc.perform(get("/api/cards").param("q", "p2"))
			.andExpect(jsonPath("$.items[*].id").value(contains(2)));
	}

	@Test
	void matchesDuctTapeSolutions() throws Exception {
		mvc.perform(get("/api/cards").param("q", "d4"))
			.andExpect(jsonPath("$.items[*].id").value(contains(4)));
	}

	@Test
	void qIsTrimmed() throws Exception {
		mvc.perform(get("/api/cards").param("q", "  flaky  "))
			.andExpect(jsonPath("$.items[*].id").value(contains(1)));
	}

	@Test
	void noMatchIsEmptyPage() throws Exception {
		mvc.perform(get("/api/cards").param("q", "kubernetes"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items").isEmpty())
			.andExpect(jsonPath("$.total_elements").value(0));
	}

	@Test
	void blankQIsIgnored() throws Exception {
		mvc.perform(get("/api/cards").param("q", "   "))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_elements").value(6));
	}

	@Test
	void combinesWithSourceFilterAndSort() throws Exception {
		mvc.perform(get("/api/cards").param("q", "hub").param("source", "github").param("sort", "newest"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(4)));
	}

	@Test
	void combinesWithMinConfidence() throws Exception {
		// "re" is in the titles of cards 4 ("retries") and 5 ("Unscored"); card 5 has no score.
		mvc.perform(get("/api/cards").param("q", "re").param("minConfidence", "10"))
			.andExpect(jsonPath("$.items[*].id").value(contains(4)));
	}

	@ParameterizedTest
	@ValueSource(strings = {"%%", "_1", "\\"})
	void likeWildcardsMatchLiterally(String q) throws Exception {
		// Unescaped, "%%" would match every card and "_1" would match "P1"/"D1"/...
		mvc.perform(get("/api/cards").param("q", q.length() < 2 ? q + q : q))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_elements").value(0));
	}

	@Test
	void sqlInjectionAttemptIsJustText() throws Exception {
		mvc.perform(get("/api/cards").param("q", "' or '1'='1"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_elements").value(0));
	}

	@ParameterizedTest
	@ValueSource(ints = {1, 101})
	void qOutsideLengthBoundsReturns400(int length) throws Exception {
		mvc.perform(get("/api/cards").param("q", "a".repeat(length)))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.parameter").value("q"));
	}

	@Test
	void singleCharAfterTrimIsRejected() throws Exception {
		mvc.perform(get("/api/cards").param("q", " p ")).andExpect(status().isBadRequest());
	}

	@Test
	void qAtMaxLengthIsAccepted() throws Exception {
		mvc.perform(get("/api/cards").param("q", "a".repeat(100))).andExpect(status().isOk());
	}
}
