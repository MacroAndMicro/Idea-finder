package com.idea_finder.repo.api;

import static org.hamcrest.Matchers.contains;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
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

/** IF-18: GET /api/stats on the seeded if_test schema. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class StatsControllerTest {

	@Autowired
	MockMvc mvc;

	@Test
	void countsPerSource() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_cards").value(6))
			.andExpect(jsonPath("$.cards_by_source.github").value(2))
			.andExpect(jsonPath("$.cards_by_source.stackexchange").value(1))
			.andExpect(jsonPath("$.cards_by_source.hackernews").value(1))
			.andExpect(jsonPath("$.cards_by_source.reddit").value(1))
			.andExpect(jsonPath("$.cards_by_source.other").value(1))
			.andExpect(jsonPath("$.total_signals").value(4))
			.andExpect(jsonPath("$.signals_by_source.github").value(1))
			.andExpect(jsonPath("$.signals_by_source.hackernews").value(1))
			.andExpect(jsonPath("$.signals_by_source.stackexchange").value(1))
			.andExpect(jsonPath("$.signals_by_source.reddit").value(1))
			.andExpect(jsonPath("$.unprocessed_signals").value(2))
			.andExpect(jsonPath("$.last_signal_fetched_at").value("2026-11-16T12:00:00Z"));
	}

	@Test
	void phase1SourcesComeFirstInStableOrder() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(jsonPath("$.cards_by_source.keys()").value(
				contains("reddit", "github", "hackernews", "stackexchange", "other")));
	}

	@Test
	void writesAreDenied() throws Exception {
		mvc.perform(post("/api/stats")).andExpect(status().isForbidden());
	}
}
