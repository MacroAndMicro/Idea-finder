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

/** IF-37: b2b filter on GET /api/cards. Fixture: 3 and 6 are not B2B, 5 is unknown (null). */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardB2bFilterTest {

	@Autowired
	MockMvc mvc;

	@Test
	void omittedIsUnfiltered() throws Exception {
		mvc.perform(get("/api/cards"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_elements").value(6));
	}

	@Test
	void blankIsUnfiltered() throws Exception {
		mvc.perform(get("/api/cards").param("b2b", " "))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_elements").value(6));
	}

	@Test
	void trueKeepsOnlyB2bCards() throws Exception {
		mvc.perform(get("/api/cards").param("b2b", "true"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(1, 2, 4)))
			.andExpect(jsonPath("$.total_elements").value(3));
	}

	@Test
	void falseKeepsOnlyNonB2bCards() throws Exception {
		mvc.perform(get("/api/cards").param("b2b", "FALSE"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(6, 3)));
	}

	@Test
	void combinesWithQ() throws Exception {
		mvc.perform(get("/api/cards").param("b2b", "true").param("q", "github"))
			.andExpect(jsonPath("$.items[*].id").value(contains(4)));
		mvc.perform(get("/api/cards").param("b2b", "false").param("q", "github"))
			.andExpect(jsonPath("$.total_elements").value(0));
	}

	@Test
	void combinesWithOtherFiltersSortAndPaging() throws Exception {
		mvc.perform(get("/api/cards").param("b2b", "true").param("source", "github")
				.param("minConfidence", "20").param("intent", "low").param("sort", "newest"))
			.andExpect(jsonPath("$.items[*].id").value(contains(4)));
		mvc.perform(get("/api/cards").param("b2b", "true").param("sort", "newest").param("size", "2").param("page", "1"))
			.andExpect(jsonPath("$.items[*].id").value(contains(1)))
			.andExpect(jsonPath("$.total_elements").value(3))
			.andExpect(jsonPath("$.total_pages").value(2));
	}

	@ParameterizedTest
	@ValueSource(strings = {"yes", "1", "maybe", "true;drop"})
	void invalidValueIs400ProblemDetail(String value) throws Exception {
		mvc.perform(get("/api/cards").param("b2b", value))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.parameter").value("b2b"))
			.andExpect(jsonPath("$.detail").value("b2b must be true or false"));
	}
}
