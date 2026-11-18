package com.idea_finder.repo.api;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasKey;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
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
	void lastRunPerSource() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.last_runs.keys()").value(
				contains("reddit", "github", "hackernews", "stackexchange")))
			// latest of two github runs, timestamp = finished_at
			.andExpect(jsonPath("$.last_runs.github.last_run_at").value("2026-11-16T00:02:00Z"))
			.andExpect(jsonPath("$.last_runs.github.last_run_status").value("Partial"))
			// no finished_at: falls back to started_at
			.andExpect(jsonPath("$.last_runs.hackernews.last_run_at").value("2026-11-16T06:00:00Z"))
			.andExpect(jsonPath("$.last_runs.hackernews.last_run_status").value("Failed"))
			.andExpect(jsonPath("$.last_runs.reddit", hasKey("last_run_at")))
			.andExpect(jsonPath("$.last_runs.reddit.last_run_at").doesNotExist())
			.andExpect(jsonPath("$.last_runs.reddit.last_run_status").doesNotExist())
			// counts and error text are never exposed
			.andExpect(content().string(not(containsString("secret-ish"))))
			.andExpect(content().string(not(containsString("error_summary"))));
	}

	@Test
	void existingFieldsUnchanged() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(jsonPath("$.keys()").value(contains("total_cards", "cards_by_source", "total_signals",
				"signals_by_source", "unprocessed_signals", "last_signal_fetched_at", "last_runs", "pipeline")));
	}

	/** IF-45: no embeddings or extractions in the base fixture, so the funnel is all zeros. */
	@Test
	void pipelineZeroWithoutExtractions() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.pipeline.keys()").value(contains("embedded_signals", "extracted_signals",
				"pain_points", "b2b_pain_points", "failed_extractions")))
			.andExpect(jsonPath("$.pipeline.embedded_signals").value(0))
			.andExpect(jsonPath("$.pipeline.extracted_signals").value(0))
			.andExpect(jsonPath("$.pipeline.pain_points").value(0))
			.andExpect(jsonPath("$.pipeline.b2b_pain_points").value(0))
			.andExpect(jsonPath("$.pipeline.failed_extractions").value(0));
	}

	/** IF-45: funnel counts over seeded embeddings and extractions. */
	@Test
	@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA, TestDb.PIPELINE}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
	void pipelineFunnelCounts() throws Exception {
		mvc.perform(get("/api/stats"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.pipeline.embedded_signals").value(3))
			.andExpect(jsonPath("$.pipeline.extracted_signals").value(4))
			.andExpect(jsonPath("$.pipeline.pain_points").value(2))
			.andExpect(jsonPath("$.pipeline.b2b_pain_points").value(1))
			.andExpect(jsonPath("$.pipeline.failed_extractions").value(1))
			// existing fields unchanged by the pipeline fixture
			.andExpect(jsonPath("$.total_signals").value(4))
			.andExpect(jsonPath("$.unprocessed_signals").value(2))
			// extraction text is never exposed
			.andExpect(content().string(not(containsString("B2B pain"))));
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
