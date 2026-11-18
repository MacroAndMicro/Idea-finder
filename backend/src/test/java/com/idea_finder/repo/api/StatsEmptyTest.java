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

	/** IF-23: every Phase 1 source is listed with null last run when ingestion_runs is empty. */
	@Test
	void lastRunsNullWhenNoRuns() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.last_runs", not(hasKey("g2"))))
			.andExpect(jsonPath("$.last_runs.reddit", hasKey("last_run_at")))
			.andExpect(jsonPath("$.last_runs.reddit", hasKey("last_run_status")))
			.andExpect(jsonPath("$.last_runs.reddit.last_run_at").doesNotExist())
			.andExpect(jsonPath("$.last_runs.github.last_run_status").doesNotExist())
			.andExpect(jsonPath("$.last_runs.hackernews.last_run_at").doesNotExist())
			.andExpect(jsonPath("$.last_runs.stackexchange.last_run_status").doesNotExist());
	}

	/** IF-45: the pipeline funnel is all zeros on an empty database. */
	@Test
	void pipelineAllZero() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.pipeline.embedded_signals").value(0))
			.andExpect(jsonPath("$.pipeline.extracted_signals").value(0))
			.andExpect(jsonPath("$.pipeline.pain_points").value(0))
			.andExpect(jsonPath("$.pipeline.b2b_pain_points").value(0))
			.andExpect(jsonPath("$.pipeline.failed_extractions").value(0));
	}
}
