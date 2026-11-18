package com.idea_finder.repo.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.hamcrest.Matchers.contains;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.OffsetDateTime;

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

/**
 * IF-77: createdSince on GET /api/cards and /api/cards/facets. Fixture created_at (UTC midnight):
 * 6 = 11-09, 1 = 11-10, 2 = 11-11, 3 = 11-12, 4 = 11-13, 5 = 11-14 (all 2026).
 */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardCreatedSinceTest {

	@Autowired
	MockMvc mvc;

	@Test
	void omittedOrBlankIsUnfiltered() throws Exception {
		mvc.perform(get("/api/cards"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_elements").value(6));
		mvc.perform(get("/api/cards").param("createdSince", " "))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total_elements").value(6));
	}

	@Test
	void dateMeansStartOfDayUtcInclusive() throws Exception {
		mvc.perform(get("/api/cards").param("createdSince", "2026-11-12").param("sort", "newest"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(5, 4, 3)))
			.andExpect(jsonPath("$.total_elements").value(3));
	}

	@Test
	void instantIsInclusiveAndHonoursOffset() throws Exception {
		mvc.perform(get("/api/cards").param("createdSince", "2026-11-11T00:00:00Z").param("sort", "newest"))
			.andExpect(jsonPath("$.items[*].id").value(contains(5, 4, 3, 2)));
		mvc.perform(get("/api/cards").param("createdSince", "2026-11-11T00:00:00.001Z"))
			.andExpect(jsonPath("$.total_elements").value(3));
		// 2026-11-12T00:00+01:00 = 2026-11-11T23:00Z: card 3 (11-12) in, card 2 (11-11) out.
		mvc.perform(get("/api/cards").param("createdSince", "2026-11-12T00:00:00+01:00").param("sort", "newest"))
			.andExpect(jsonPath("$.items[*].id").value(contains(5, 4, 3)));
	}

	@Test
	void futureDateReturnsEmpty() throws Exception {
		mvc.perform(get("/api/cards").param("createdSince", "2999-01-01"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items").isEmpty())
			.andExpect(jsonPath("$.total_elements").value(0));
		mvc.perform(get("/api/cards/facets").param("createdSince", "2999-01-01"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(0))
			.andExpect(jsonPath("$.source_platform.github").value(0));
	}

	@Test
	void combinesWithQAndSource() throws Exception {
		mvc.perform(get("/api/cards").param("createdSince", "2026-11-13").param("q", "github"))
			.andExpect(jsonPath("$.items[*].id").value(contains(4)));
		mvc.perform(get("/api/cards").param("createdSince", "2026-11-14").param("q", "github"))
			.andExpect(jsonPath("$.total_elements").value(0));
		mvc.perform(get("/api/cards").param("createdSince", "2026-11-10").param("source", "github")
				.param("sort", "newest"))
			.andExpect(jsonPath("$.items[*].id").value(contains(4, 1)));
		mvc.perform(get("/api/cards").param("createdSince", "2026-11-11").param("source", "github")
				.param("intent", "low").param("b2b", "true").param("minConfidence", "20"))
			.andExpect(jsonPath("$.items[*].id").value(contains(4)));
	}

	@Test
	void facetsApplyCreatedSinceToTotalAndEveryFacet() throws Exception {
		mvc.perform(get("/api/cards/facets").param("createdSince", "2026-11-12"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(3))
			.andExpect(jsonPath("$.source_platform.github").value(1))
			.andExpect(jsonPath("$.source_platform.hackernews").value(1))
			.andExpect(jsonPath("$.source_platform.reddit").value(1))
			.andExpect(jsonPath("$.source_platform.stackexchange").value(0))
			.andExpect(jsonPath("$.economic_intent.High").value(1))
			.andExpect(jsonPath("$.economic_intent.Low").value(1))
			.andExpect(jsonPath("$.economic_intent.Medium").value(0))
			.andExpect(jsonPath("$.is_b2b_filtered.true").value(1))
			.andExpect(jsonPath("$.is_b2b_filtered.false").value(1));
	}

	@Test
	void facetsCombineWithQAndSource() throws Exception {
		mvc.perform(get("/api/cards/facets").param("createdSince", "2026-11-10").param("source", "github"))
			.andExpect(jsonPath("$.total").value(2))
			// the source facet ignores source but keeps createdSince: cards 1-5 (card 6 is older)
			.andExpect(jsonPath("$.source_platform.github").value(2))
			.andExpect(jsonPath("$.source_platform.stackexchange").value(1))
			.andExpect(jsonPath("$.source_platform.reddit").value(1));
		mvc.perform(get("/api/cards/facets").param("createdSince", "2026-11-13").param("q", "github"))
			.andExpect(jsonPath("$.total").value(1))
			.andExpect(jsonPath("$.source_platform.github").value(1));
	}

	@ParameterizedTest
	@ValueSource(strings = {"yesterday", "2026-13-01", "2026-02-30", "2026-11-12T00:00:00", "16/11/2026",
		"2026-11-12 00:00:00Z", "+12026-11-12", "0000-01-01", "2026-11-12T00:00:00Z;drop", "1700000000"})
	void invalidValueIs400ProblemDetail(String value) throws Exception {
		for (String path : new String[] {"/api/cards", "/api/cards/facets"}) {
			mvc.perform(get(path).param("createdSince", value))
				.andExpect(status().isBadRequest())
				.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
				.andExpect(jsonPath("$.parameter").value("createdSince"));
		}
	}

	@Test
	void parserAcceptsDateAndOffsetInstantOnly() {
		assertThat(CardQueryService.parseCreatedSince(null)).isNull();
		assertThat(CardQueryService.parseCreatedSince("  ")).isNull();
		assertThat(CardQueryService.parseCreatedSince(" 2026-11-16 "))
			.isEqualTo(OffsetDateTime.parse("2026-11-16T00:00:00Z"));
		assertThat(CardQueryService.parseCreatedSince("2026-11-16T08:30:00-05:00").toInstant())
			.isEqualTo(OffsetDateTime.parse("2026-11-16T13:30:00Z").toInstant());
		assertThatThrownBy(() -> CardQueryService.parseCreatedSince("x".repeat(500)))
			.isInstanceOf(InvalidParameterException.class);
	}
}
