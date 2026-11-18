package com.idea_finder.repo.api;

import static org.assertj.core.api.Assertions.assertThatException;
import static org.hamcrest.Matchers.containsString;
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
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
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

	/**
	 * IF-70: 400 matrix. Each case names the offending parameter; the body is a ProblemDetail and
	 * never leaks internals (exception class names, SQL, stack traces).
	 */
	@ParameterizedTest(name = "{0}={1} -> 400 on {0}")
	@CsvSource(delimiter = '|', value = {
		"source        | g2x",
		"source        | REDDIT_",
		"source        | g2,github",
		"intent        | huge",
		"intent        | 1",
		"intent        | High,Low",
		"minConfidence | -1",
		"minConfidence | 100.01",
		"minConfidence | 101",
		"b2b           | yes",
		"b2b           | 1",
		"b2b           | truee",
		"q             | x",
		"q             | ' a '"
	})
	void invalidValueIs400NamingTheParameter(String name, String value) throws Exception {
		expectCleanProblem(get("/api/cards/facets").param(name, value))
			.andExpect(jsonPath("$.title").value("Invalid request parameter"))
			.andExpect(jsonPath("$.parameter").value(name));
	}

	@Test
	void overLongQueryIs400() throws Exception {
		expectCleanProblem(get("/api/cards/facets").param("q", "a".repeat(CardQueryService.MAX_Q + 1)))
			.andExpect(jsonPath("$.parameter").value("q"));
	}

	@ParameterizedTest(name = "minConfidence={0} -> 400")
	@CsvSource({"abc", "NaN", "1e", "50%"})
	void nonNumericMinConfidenceIs400(String value) throws Exception {
		expectCleanProblem(get("/api/cards/facets").param("minConfidence", value));
	}

	@Test
	void firstInvalidParameterWinsWhenSeveralAreBad() throws Exception {
		// Validation order in CardQueryService.facets: q, source, minConfidence, intent, b2b.
		expectCleanProblem(get("/api/cards/facets").param("source", "nope").param("b2b", "maybe"))
			.andExpect(jsonPath("$.parameter").value("source"));
	}

	@ParameterizedTest(name = "{0} -> 200")
	@CsvSource(delimiter = '|', value = {
		"source=GitHub",
		"source=stackexchange&intent=medium&b2b=TRUE",
		"intent=unspecified&b2b=false",
		"minConfidence=0",
		"minConfidence=100",
		"minConfidence=55.5&b2b=true",
		"q=gh&source=github&minConfidence=10&intent=Low&b2b=true",
		"q=ab&source="
	})
	void validCombinationsAre200(String query) throws Exception {
		mvc.perform(get("/api/cards/facets?" + query))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").isNumber());
	}

	@Test
	void blankParametersMeanNoFilter() throws Exception {
		mvc.perform(get("/api/cards/facets")
				.param("q", " ").param("source", " ").param("intent", " ").param("b2b", " "))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(6));
	}

	private ResultActions expectCleanProblem(
			MockHttpServletRequestBuilder request) throws Exception {
		return mvc.perform(request)
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(400))
			.andExpect(jsonPath("$", not(hasKey("trace"))))
			.andExpect(jsonPath("$", not(hasKey("exception"))))
			.andExpect(content().string(not(containsString("Exception"))))
			.andExpect(content().string(not(containsString("SQL"))))
			.andExpect(content().string(not(containsString("at com."))));
	}
}
