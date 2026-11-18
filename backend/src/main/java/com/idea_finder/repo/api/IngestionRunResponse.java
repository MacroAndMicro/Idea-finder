package com.idea_finder.repo.api;

import java.time.OffsetDateTime;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.idea_finder.repo.domain.IngestionRun;

/** IF-36: one ingestion run as exposed by GET /api/ingestion-runs. */
public record IngestionRunResponse(
		long id,
		@JsonProperty("source_platform") String sourcePlatform,
		@JsonProperty("started_at") OffsetDateTime startedAt,
		@JsonProperty("finished_at") OffsetDateTime finishedAt,
		String status,
		@JsonProperty("fetched_count") int fetchedCount,
		@JsonProperty("inserted_count") int insertedCount,
		@JsonProperty("skipped_count") int skippedCount,
		@JsonProperty("error_summary") String errorSummary) {

	/** Defence in depth: error_summary is meant to be short; never echo an unbounded blob. */
	static final int MAX_ERROR_SUMMARY = 500;

	static IngestionRunResponse from(IngestionRun r) {
		return new IngestionRunResponse(
			r.getId(),
			r.getSourcePlatform().dbValue(),
			r.getStartedAt(),
			r.getFinishedAt(),
			r.getStatus(),
			r.getFetchedCount(),
			r.getInsertedCount(),
			r.getSkippedCount(),
			truncate(r.getErrorSummary()));
	}

	static String truncate(String s) {
		if (s == null || s.length() <= MAX_ERROR_SUMMARY) {
			return s;
		}
		int end = MAX_ERROR_SUMMARY;
		if (Character.isHighSurrogate(s.charAt(end - 1))) {
			end--; // don't split a surrogate pair
		}
		return s.substring(0, end) + "…";
	}
}
