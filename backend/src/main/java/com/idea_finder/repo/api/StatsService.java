package com.idea_finder.repo.api;

import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.domain.IngestionRun;
import com.idea_finder.repo.domain.IngestionRunRepository;
import com.idea_finder.repo.domain.OpportunityCardRepository;
import com.idea_finder.repo.domain.RawSignalRepository;
import com.idea_finder.repo.domain.SourcePlatform;

/** Aggregate counts over cards and raw signals (a handful of COUNT queries, no caching yet). */
@Service
@Transactional(readOnly = true)
public class StatsService {

	/** Always present in the per-source maps, with 0 when a source has no rows. */
	static final List<SourcePlatform> PHASE_1_SOURCES = List.of(
		SourcePlatform.REDDIT, SourcePlatform.GITHUB, SourcePlatform.HACKERNEWS, SourcePlatform.STACKEXCHANGE);

	private final OpportunityCardRepository cards;
	private final RawSignalRepository signals;
	private final IngestionRunRepository runs;

	public StatsService(OpportunityCardRepository cards, RawSignalRepository signals, IngestionRunRepository runs) {
		this.cards = cards;
		this.signals = signals;
		this.runs = runs;
	}

	public StatsResponse stats() {
		return new StatsResponse(
			cards.count(),
			bySource(cards.countBySource()),
			signals.count(),
			bySource(signals.countBySource()),
			signals.countByProcessedAtIsNull(),
			signals.lastFetchedAt(),
			lastRuns(runs.findLatestPerSource()));
	}

	/** Phase 1 sources first (null when never run), then any other source that has runs. */
	static Map<String, StatsResponse.LastRun> lastRuns(List<IngestionRun> latest) {
		Map<String, StatsResponse.LastRun> result = new LinkedHashMap<>();
		PHASE_1_SOURCES.forEach(p -> result.put(p.dbValue(), StatsResponse.LastRun.NEVER));
		// Ties on started_at: the higher id (inserted later) wins.
		latest.stream()
			.sorted(Comparator.comparing(IngestionRun::getId))
			.forEach(r -> result.put(r.getSourcePlatform().dbValue(),
				new StatsResponse.LastRun(r.lastActivityAt(), r.getStatus())));
		return Collections.unmodifiableMap(result);
	}

	/** Phase 1 sources first (zero-filled), then any other source that actually has rows. */
	static Map<String, Long> bySource(List<Object[]> rows) {
		Map<String, Long> result = new LinkedHashMap<>();
		PHASE_1_SOURCES.forEach(p -> result.put(p.dbValue(), 0L));
		for (Object[] row : rows) {
			result.put(((SourcePlatform) row[0]).dbValue(), (Long) row[1]);
		}
		return Collections.unmodifiableMap(result);
	}
}
