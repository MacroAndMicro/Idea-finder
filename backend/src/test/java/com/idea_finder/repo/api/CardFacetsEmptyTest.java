package com.idea_finder.repo.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
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

/** IF-53: GET /api/cards/facets on an empty if_test schema returns zero counts, not 404. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = TestDb.SCHEMA, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardFacetsEmptyTest {

	@Autowired
	MockMvc mvc;

	@Test
	void allZero() throws Exception {
		mvc.perform(get("/api/cards/facets").param("source", "github"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(0))
			.andExpect(jsonPath("$.source_platform.reddit").value(0))
			.andExpect(jsonPath("$.source_platform.github").value(0))
			.andExpect(jsonPath("$.source_platform.hackernews").value(0))
			.andExpect(jsonPath("$.source_platform.stackexchange").value(0))
			.andExpect(jsonPath("$.economic_intent.High").value(0))
			.andExpect(jsonPath("$.economic_intent.Medium").value(0))
			.andExpect(jsonPath("$.economic_intent.Low").value(0))
			.andExpect(jsonPath("$.economic_intent.Unspecified").value(0))
			.andExpect(jsonPath("$.is_b2b_filtered.true").value(0))
			.andExpect(jsonPath("$.is_b2b_filtered.false").value(0));
	}
}
