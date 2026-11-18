package com.idea_finder.repo.api;

import static org.assertj.core.api.Assertions.assertThatException;
import static org.hamcrest.Matchers.hasKey;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.TestDb;
import com.idea_finder.repo.domain.OpportunityCardRepository;

/**
 * IF-53: GET /api/cards/facets. Fixture: 1 github/High/90/B2B, 2 stackexchange/Medium/70/B2B,
 * 3 hackernews/High/55/not, 4 github/Low/30/B2B, 5 reddit/null/null/null, 6 other/Unspecified/70/not.
 */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardFacetsControllerTest {

	@Autowired
	MockMvc mvc;

	@Autowired
	OpportunityCardRepository repository;

	@Test
	void onlyWhitelistedAttributesCanBeGrouped() {
		// The repository proxy may wrap the IllegalArgumentException in a DataAccessException.
		assertThatException()
			.isThrownBy(() -> repository.countGroupedBy("problemStatement",
				OpportunityCardRepository.filters(null, null, null, null, null)))
			.withMessageContaining("Not a facet attribute");
	}

	@Test
	void unfilteredCountsEveryCard() throws Exception {
		mvc.perform(get("/api/cards/facets"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(6))
			.andExpect(jsonPath("$.source_platform.reddit").value(1))
			.andExpect(jsonPath("$.source_platform.github").value(2))
			.andExpect(jsonPath("$.source_platform.hackernews").value(1))
			.andExpect(jsonPath("$.source_platform.stackexchange").value(1))
			.andExpect(jsonPath("$.source_platform.other").value(1))
			.andExpect(jsonPath("$.source_platform", not(hasKey("g2"))))
			.andExpect(jsonPath("$.economic_intent.High").value(2))
			.andExpect(jsonPath("$.economic_intent.Medium").value(1))
			.andExpect(jsonPath("$.economic_intent.Low").value(1))
			.andExpect(jsonPath("$.economic_intent.Unspecified").value(1))
			.andExpect(jsonPath("$.is_b2b_filtered.true").value(3))
			.andExpect(jsonPath("$.is_b2b_filtered.false").value(2));
	}

	@Test
	void sourceFilterIgnoredBySourceFacet() throws Exception {
		mvc.perform(get("/api/cards/facets").param("source", "github"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(2))
			.andExpect(jsonPath("$.source_platform.github").value(2))
			.andExpect(jsonPath("$.source_platform.reddit").value(1))
			.andExpect(jsonPath("$.economic_intent.High").value(1))
			.andExpect(jsonPath("$.economic_intent.Low").value(1))
			.andExpect(jsonPath("$.economic_intent.Medium").value(0))
			.andExpect(jsonPath("$.is_b2b_filtered.true").value(2))
			.andExpect(jsonPath("$.is_b2b_filtered.false").value(0));
	}

	@Test
	void intentFilterIgnoredByIntentFacet() throws Exception {
		mvc.perform(get("/api/cards/facets").param("intent", "high"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(2))
			.andExpect(jsonPath("$.source_platform.github").value(1))
			.andExpect(jsonPath("$.source_platform.hackernews").value(1))
			.andExpect(jsonPath("$.source_platform.reddit").value(0))
			.andExpect(jsonPath("$.source_platform", not(hasKey("other"))))
			.andExpect(jsonPath("$.economic_intent.High").value(2))
			.andExpect(jsonPath("$.economic_intent.Medium").value(1))
			.andExpect(jsonPath("$.is_b2b_filtered.true").value(1))
			.andExpect(jsonPath("$.is_b2b_filtered.false").value(1));
	}

	@Test
	void b2bFilterIgnoredByB2bFacet() throws Exception {
		mvc.perform(get("/api/cards/facets").param("b2b", "true"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(3))
			.andExpect(jsonPath("$.source_platform.github").value(2))
			.andExpect(jsonPath("$.source_platform.stackexchange").value(1))
			.andExpect(jsonPath("$.source_platform.hackernews").value(0))
			.andExpect(jsonPath("$.economic_intent.High").value(1))
			.andExpect(jsonPath("$.economic_intent.Unspecified").value(0))
			.andExpect(jsonPath("$.is_b2b_filtered.true").value(3))
			.andExpect(jsonPath("$.is_b2b_filtered.false").value(2));
	}

	@Test
	void minConfidenceAppliesToEveryFacet() throws Exception {
		mvc.perform(get("/api/cards/facets").param("minConfidence", "60"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(3))
			.andExpect(jsonPath("$.source_platform.github").value(1))
			.andExpect(jsonPath("$.source_platform.stackexchange").value(1))
			.andExpect(jsonPath("$.source_platform.other").value(1))
			.andExpect(jsonPath("$.source_platform.hackernews").value(0))
			.andExpect(jsonPath("$.economic_intent.Low").value(0))
			.andExpect(jsonPath("$.economic_intent.Unspecified").value(1))
			.andExpect(jsonPath("$.is_b2b_filtered.true").value(2))
			.andExpect(jsonPath("$.is_b2b_filtered.false").value(1));
	}

	@Test
	void keywordAppliesToEveryFacet() throws Exception {
		mvc.perform(get("/api/cards/facets").param("q", "github"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(1))
			.andExpect(jsonPath("$.source_platform.github").value(1))
			.andExpect(jsonPath("$.source_platform.reddit").value(0))
			.andExpect(jsonPath("$.economic_intent.Low").value(1))
			.andExpect(jsonPath("$.is_b2b_filtered.true").value(1));
	}

	@Test
	void totalMatchesListEndpoint() throws Exception {
		mvc.perform(get("/api/cards").param("source", "github").param("b2b", "true"))
			.andExpect(jsonPath("$.total_elements").value(2));
		mvc.perform(get("/api/cards/facets").param("source", "github").param("b2b", "true"))
			.andExpect(jsonPath("$.total").value(2));
	}

	@ParameterizedTest
	@CsvSource({
		"q, x",
		"source, g3",
		"minConfidence, 101",
		"minConfidence, abc",
		"intent, huge",
		"b2b, yes"
	})
	void invalidParamIs400ProblemDetail(String name, String value) throws Exception {
		mvc.perform(get("/api/cards/facets").param(name, value))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(400));
	}

	@Test
	void invalidParamMatchesListEndpointError() throws Exception {
		mvc.perform(get("/api/cards/facets").param("intent", "huge"))
			.andExpect(jsonPath("$.parameter").value("intent"))
			.andExpect(jsonPath("$.title").value("Invalid request parameter"));
	}
}
