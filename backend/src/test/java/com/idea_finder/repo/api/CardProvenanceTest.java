package com.idea_finder.repo.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasKey;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.OffsetDateTime;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.TestDb;
import com.idea_finder.repo.domain.OpportunityCard;
import com.idea_finder.repo.domain.OpportunityCardRepository;

/** IF-35: card provenance / signal spread columns and sort=recent. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardProvenanceTest {

	@Autowired
	MockMvc mvc;

	@Autowired
	OpportunityCardRepository repository;

	@Test
	void repositoryMapsProvenanceColumns() {
		OpportunityCard card = repository.findById(1L).orElseThrow();
		assertThat(card.getSignalCount()).isEqualTo(2);
		assertThat(card.getPlatformCount()).isEqualTo(2);
		assertThat(card.getFirstSeenAt()).isEqualTo(OffsetDateTime.parse("2026-11-01T00:00:00Z"));
		assertThat(card.getLastSeenAt()).isEqualTo(OffsetDateTime.parse("2026-11-05T00:00:00Z"));
		assertThat(card.getLlmModel()).isEqualTo("internal-llm-model");
		assertThat(card.getPromptVersion()).isEqualTo("internal-prompt-v1");

		OpportunityCard empty = repository.findById(5L).orElseThrow();
		assertThat(empty.getSignalCount()).isNull();
		assertThat(empty.getLastSeenAt()).isNull();
	}

	@Test
	void cardJsonExposesSpreadButNotModelOrPrompt() throws Exception {
		mvc.perform(get("/api/cards/1"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.signal_count").value(2))
			.andExpect(jsonPath("$.platform_count").value(2))
			.andExpect(jsonPath("$.first_seen_at").value("2026-11-01T00:00:00Z"))
			.andExpect(jsonPath("$.last_seen_at").value("2026-11-05T00:00:00Z"))
			.andExpect(jsonPath("$", not(hasKey("llm_model"))))
			.andExpect(jsonPath("$", not(hasKey("prompt_version"))))
			.andExpect(jsonPath("$", not(hasKey("llmModel"))))
			.andExpect(content().string(not(containsString("internal-llm-model"))))
			.andExpect(content().string(not(containsString("internal-prompt-v1"))));
	}

	@Test
	void unpopulatedSpreadIsNull() throws Exception {
		mvc.perform(get("/api/cards/5"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$", hasKey("signal_count")))
			.andExpect(jsonPath("$.signal_count").doesNotExist())
			.andExpect(jsonPath("$.last_seen_at").doesNotExist());
	}

	@Test
	void listItemsCarrySpreadToo() throws Exception {
		mvc.perform(get("/api/cards").param("source", "stackexchange"))
			.andExpect(jsonPath("$.items[0].signal_count").value(1))
			.andExpect(jsonPath("$.items[0].platform_count").value(1))
			.andExpect(content().string(not(containsString("prompt_version"))));
	}

	@Test
	void sortRecentIsLastSeenDescNullsLastThenIdDesc() throws Exception {
		// last_seen_at: 4 (11-07) > 1 (11-05) > 2 (11-02); 3, 5, 6 have none -> id desc.
		mvc.perform(get("/api/cards").param("sort", "recent"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(4, 1, 2, 6, 5, 3)));
	}

	@Test
	void sortRecentIsCaseInsensitiveAndPages() throws Exception {
		mvc.perform(get("/api/cards").param("sort", "RECENT").param("size", "2").param("page", "1"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(2, 6)));
	}

	@Test
	void existingSortsUnchanged() throws Exception {
		mvc.perform(get("/api/cards").param("sort", "newest"))
			.andExpect(jsonPath("$.items[*].id").value(contains(5, 4, 3, 2, 1, 6)));
		mvc.perform(get("/api/cards"))
			.andExpect(jsonPath("$.items[*].id").value(contains(1, 2, 6, 3, 4, 5)));
	}

	@Test
	void invalidSortStill400AndListsRecent() throws Exception {
		mvc.perform(get("/api/cards").param("sort", "oldest"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.parameter").value("sort"))
			.andExpect(jsonPath("$.detail").value(containsString("recent")));
	}
}
