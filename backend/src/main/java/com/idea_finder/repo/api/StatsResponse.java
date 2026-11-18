package com.idea_finder.repo.api;

import java.time.OffsetDateTime;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.idea_finder.repo.domain.PipelineCounts;

/** Ingestion health snapshot. Maps are keyed by source_platform value. */
public record StatsResponse(
		@JsonProperty("total_cards") long totalCards,
		@JsonProperty("cards_by_source") Map<String, Long> cardsBySource,
		@JsonProperty("total_signals") long totalSignals,
		@JsonProperty("signals_by_source") Map<String, Long> signalsBySource,
		@JsonProperty("unprocessed_signals") long unprocessedSignals,
		@JsonInclude(JsonInclude.Include.ALWAYS)
		@JsonProperty("last_signal_fetched_at") OffsetDateTime lastSignalFetchedAt,
		@JsonProperty("last_runs") Map<String, LastRun> lastRuns,
		@JsonProperty("pipeline") Pipeline pipeline) {

	/**
	 * IF-45: how far raw signals got through the pipeline. failed_extractions = extractions
	 * whose is_pain_point is null (the LLM call or parse failed).
	 */
	public record Pipeline(
			@JsonProperty("embedded_signals") long embeddedSignals,
			@JsonProperty("extracted_signals") long extractedSignals,
			@JsonProperty("pain_points") long painPoints,
			@JsonProperty("b2b_pain_points") long b2bPainPoints,
			@JsonProperty("failed_extractions") long failedExtractions) {

		static Pipeline of(PipelineCounts c) {
			return new Pipeline(c.getEmbeddedSignals(), c.getExtractedSignals(), c.getPainPoints(),
				c.getB2bPainPoints(), c.getFailedExtractions());
		}
	}

	/** Latest ingestion run of one source (IF-23); both fields are null when it never ran. */
	@JsonInclude(JsonInclude.Include.ALWAYS)
	public record LastRun(
			@JsonProperty("last_run_at") OffsetDateTime lastRunAt,
			@JsonProperty("last_run_status") String lastRunStatus) {

		static final LastRun NEVER = new LastRun(null, null);
	}
}
