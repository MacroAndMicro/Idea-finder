package com.idea_finder.repo.api;

import static org.hamcrest.Matchers.hasKey;
import static org.hamcrest.Matchers.not;
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

/** IF-18: GET /api/stats on an empty if_test schema. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = TestDb.SCHEMA, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class StatsEmptyTest {

	@Autowired
	MockMvc mvc;

	@Test
	void allZeroWithPhase1SourcesPresent() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_cards").value(0))
			.andExpect(jsonPath("$.total_signals").value(0))
			.andExpect(jsonPath("$.unprocessed_signals").value(0))
			.andExpect(jsonPath("$", hasKey("last_signal_fetched_at")))
			.andExpect(jsonPath("$.last_signal_fetched_at").doesNotExist())
			.andExpect(jsonPath("$.cards_by_source.reddit").value(0))
			.andExpect(jsonPath("$.cards_by_source.github").value(0))
			.andExpect(jsonPath("$.cards_by_source.hackernews").value(0))
			.andExpect(jsonPath("$.cards_by_source.stackexchange").value(0))
			.andExpect(jsonPath("$.cards_by_source", not(hasKey("g2"))))
			.andExpect(jsonPath("$.signals_by_source.reddit").value(0))
			.andExpect(jsonPath("$.signals_by_source.github").value(0))
			.andExpect(jsonPath("$.signals_by_source.hackernews").value(0))
			.andExpect(jsonPath("$.signals_by_source.stackexchange").value(0));
	}
}
