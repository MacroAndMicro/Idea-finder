package com.idea_finder.repo.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;

import com.idea_finder.repo.TestDb;

/** Runs against the real Postgres from DATABASE_URL (the CI service), not an embedded DB. */
@DataJpaTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class OpportunityCardRepositoryTest {

	@Autowired
	OpportunityCardRepository repository;

	private static final PageRequest FIRST_PAGE = PageRequest.of(0, 50, Sort.by("id"));

	@Test
	void mapsEveryColumnExceptEmbedding() {
		OpportunityCard card = repository.findById(1L).orElseThrow();
		assertThat(card.getTitle()).isEqualTo("CI flaky test triage");
		assertThat(card.getSourcePlatform()).isEqualTo(SourcePlatform.GITHUB);
		assertThat(card.getSourceUrl()).isEqualTo("https://github.com/o/r/issues/1");
		assertThat(card.getRawContentSnippet()).isEqualTo("snippet 1");
		assertThat(card.getProblemStatement()).isEqualTo("P1");
		assertThat(card.getTriggerContext()).isEqualTo("T1");
		assertThat(card.getMarketSize()).isEqualTo("M1");
		assertThat(card.getDuctTapeSolutions()).isEqualTo("D1");
		assertThat(card.getEconomicIntent()).isEqualTo(EconomicIntent.HIGH);
		assertThat(card.getMvpWedge()).isEqualTo("W1");
		assertThat(card.getConfidenceScore()).isEqualByComparingTo("90");
		assertThat(card.getStatus()).isEqualTo("Backlog");
		assertThat(card.getB2bFiltered()).isTrue();
		assertThat(card.getEmbeddingModel()).isEqualTo("m");
		assertThat(card.getCreatedAt()).isNotNull();
		assertThat(card.getUpdatedAt()).isNotNull();
	}

	@Test
	void nullableFieldsMapToNull() {
		OpportunityCard card = repository.findById(5L).orElseThrow();
		assertThat(card.getEconomicIntent()).isNull();
		assertThat(card.getConfidenceScore()).isNull();
	}

	@Test
	void missingIdIsEmpty() {
		assertThat(repository.findById(999L)).isEmpty();
	}

	@Test
	void noFiltersReturnsAll() {
		assertThat(repository.search(null, null, null, FIRST_PAGE).getTotalElements()).isEqualTo(6);
	}

	@Test
	void filtersBySource() {
		Page<OpportunityCard> page = repository.search(SourcePlatform.GITHUB, null, null, FIRST_PAGE);
		assertThat(page.getContent()).extracting(OpportunityCard::getId).containsExactly(1L, 4L);
	}

	@Test
	void filtersByMinConfidenceAndExcludesUnscored() {
		Page<OpportunityCard> page = repository.search(null, new BigDecimal("70"), null, FIRST_PAGE);
		assertThat(page.getContent()).extracting(OpportunityCard::getId).containsExactly(1L, 2L, 6L);
	}

	@Test
	void filtersByIntent() {
		Page<OpportunityCard> page = repository.search(null, null, EconomicIntent.HIGH, FIRST_PAGE);
		assertThat(page.getContent()).extracting(OpportunityCard::getId).containsExactly(1L, 3L);
	}

	@Test
	void combinesFilters() {
		Page<OpportunityCard> page = repository.search(
			SourcePlatform.GITHUB, new BigDecimal("50"), EconomicIntent.HIGH, FIRST_PAGE);
		assertThat(page.getContent()).extracting(OpportunityCard::getId).containsExactly(1L);
	}

	@Test
	void pages() {
		Page<OpportunityCard> page = repository.search(null, null, null, PageRequest.of(1, 4, Sort.by("id")));
		assertThat(page.getTotalElements()).isEqualTo(6);
		assertThat(page.getTotalPages()).isEqualTo(2);
		assertThat(page.getContent()).extracting(OpportunityCard::getId).containsExactly(5L, 6L);
	}
}
