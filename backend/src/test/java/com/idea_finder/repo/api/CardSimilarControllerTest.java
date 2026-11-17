package com.idea_finder.repo.api;

import static org.hamcrest.Matchers.closeTo;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.TestDb;

/** IF-24: GET /api/cards/{id}/similar on the seeded if_test schema with fixture vectors. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA, TestDb.EMBEDDINGS}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardSimilarControllerTest {

	@Autowired
	MockMvc mvc;

	@Test
	void nearestFirstExcludingSelfAndNullEmbeddings() throws Exception {
		mvc.perform(get("/api/cards/1/similar"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$[*].id").value(contains(2, 3, 4, 5)))
			.andExpect(jsonPath("$[0].similarity").value(closeTo(0.995, 0.001)))
			.andExpect(jsonPath("$[1].similarity").value(closeTo(0.7071, 0.001)))
			.andExpect(jsonPath("$[2].similarity").value(0.0))
			// opposite vector is clamped to 0, never negative
			.andExpect(jsonPath("$[3].similarity").value(0.0));
	}

	@Test
	void usesCardResponseShapeWithoutEmbedding() throws Exception {
		mvc.perform(get("/api/cards/1/similar?limit=1"))
			.andExpect(jsonPath("$", hasSize(1)))
			.andExpect(jsonPath("$[0].id").value(2))
			.andExpect(jsonPath("$[0].title").value("Stack Exchange quota"))
			.andExpect(jsonPath("$[0].problem_statement").value("P2"))
			.andExpect(jsonPath("$[0].source_platform").value("stackexchange"))
			.andExpect(content().string(not(containsString("embedding"))));
	}

	@Test
	void limitRestrictsResults() throws Exception {
		mvc.perform(get("/api/cards/1/similar?limit=2"))
			.andExpect(jsonPath("$[*].id").value(contains(2, 3)));
	}

	@Test
	void maxLimitAccepted() throws Exception {
		mvc.perform(get("/api/cards/1/similar?limit=20"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$", hasSize(4)));
	}

	@Test
	void emptyWhenCardHasNoEmbedding() throws Exception {
		mvc.perform(get("/api/cards/6/similar"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$", hasSize(0)));
	}

	@Test
	void unknownCardIs404() throws Exception {
		mvc.perform(get("/api/cards/999/similar"))
			.andExpect(status().isNotFound())
			.andExpect(jsonPath("$.title").value("Card not found"));
	}

	@Test
	void limitOutOfRangeIs400() throws Exception {
		mvc.perform(get("/api/cards/1/similar?limit=21"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.parameter").value("limit"));
		mvc.perform(get("/api/cards/1/similar?limit=0"))
			.andExpect(status().isBadRequest());
		mvc.perform(get("/api/cards/1/similar?limit=abc"))
			.andExpect(status().isBadRequest());
	}
}
