package com.idea_finder.repo.api;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.idea_finder.repo.domain.EconomicIntent;

/**
 * IF-53: card counts per filter option. {@code total} = cards matching every filter; each map
 * ignores its own filter. Phase 1 sources, every intent and both B2B values are always present (0
 * when empty); other sources appear only when they have cards.
 */
public record FacetsResponse(
		@JsonProperty("total") long total,
		@JsonProperty("source_platform") Map<String, Long> sourcePlatform,
		@JsonProperty("economic_intent") Map<String, Long> economicIntent,
		@JsonProperty("is_b2b_filtered") Map<String, Long> b2bFiltered) {

	static FacetsResponse of(long total, List<Object[]> bySource, List<Object[]> byIntent, List<Object[]> byB2b) {
		return new FacetsResponse(total,
			StatsService.bySource(bySource.stream().filter(r -> r[0] != null).toList()),
			intents(byIntent),
			b2b(byB2b));
	}

	static Map<String, Long> intents(List<Object[]> rows) {
		Map<String, Long> result = new LinkedHashMap<>();
		for (EconomicIntent i : EconomicIntent.values()) {
			result.put(i.dbValue(), 0L);
		}
		for (Object[] row : rows) {
			if (row[0] != null) {
				result.put(((EconomicIntent) row[0]).dbValue(), ((Number) row[1]).longValue());
			}
		}
		return Collections.unmodifiableMap(result);
	}

	static Map<String, Long> b2b(List<Object[]> rows) {
		Map<String, Long> result = new LinkedHashMap<>();
		result.put("true", 0L);
		result.put("false", 0L);
		for (Object[] row : rows) {
			if (row[0] != null) {
				result.put(row[0].toString(), ((Number) row[1]).longValue());
			}
		}
		return Collections.unmodifiableMap(result);
	}
}
