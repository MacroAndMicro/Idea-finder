package com.idea_finder.repo.domain;

import java.time.OffsetDateTime;
import java.util.List;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/** Read-only repository: no save/delete methods are exposed. */
public interface RawSignalRepository extends Repository<RawSignal, Long> {

	long count();

	long countByProcessedAtIsNull();

	/** Rows of [SourcePlatform, Long count]. */
	@Query("select s.sourcePlatform, count(s) from RawSignal s group by s.sourcePlatform")
	List<Object[]> countBySource();

	@Query("select max(s.fetchedAt) from RawSignal s")
	OffsetDateTime lastFetchedAt();

	/**
	 * IF-45: pipeline funnel in one round trip (one scan of raw_signals, one of signal_extractions).
	 * An extraction whose is_pain_point is null is a failed extraction.
	 */
	@Query(nativeQuery = true, value = """
		select
		  (select count(*) from {h-schema}raw_signals s where s.embedding is not null) as embeddedSignals,
		  count(e.id)                                                  as extractedSignals,
		  count(*) filter (where e.is_pain_point)                      as painPoints,
		  count(*) filter (where e.is_pain_point and e.is_b2b)         as b2bPainPoints,
		  count(e.id) filter (where e.is_pain_point is null)           as failedExtractions
		from {h-schema}signal_extractions e
		""")
	PipelineCounts pipelineCounts();

	/** Signals linked to a card through card_signals; ordering comes from the pageable's sort. */
	@Query("""
		select s from RawSignal s
		where exists (select 1 from CardSignal cs where cs.signalId = s.id and cs.cardId = :cardId)
		""")
	Page<RawSignal> findByCardId(@Param("cardId") long cardId, Pageable pageable);
}
