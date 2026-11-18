package com.idea_finder.repo.domain;

import java.time.OffsetDateTime;

import org.hibernate.annotations.Immutable;

import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * Read-only view of public.ingestion_runs (IF-23), written only by the ingestion pipeline.
 * GET /api/stats exposes only when each source last ran and how it ended; the full row
 * (counts, error_summary) is exposed only by GET /api/ingestion-runs (IF-36).
 */
@Entity
@Immutable
@Table(name = "ingestion_runs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class IngestionRun {

	@Id
	private Long id;

	@Convert(converter = SourcePlatformConverter.class)
	@Column(name = "source_platform", nullable = false)
	private SourcePlatform sourcePlatform;

	@Column(name = "started_at", nullable = false)
	private OffsetDateTime startedAt;

	@Column(name = "finished_at")
	private OffsetDateTime finishedAt;

	/** Success, Partial or Failed (CHECK constraint). */
	@Column(name = "status", nullable = false)
	private String status;

	@Column(name = "fetched_count", nullable = false)
	private int fetchedCount;

	@Column(name = "inserted_count", nullable = false)
	private int insertedCount;

	@Column(name = "skipped_count", nullable = false)
	private int skippedCount;

	/** Short failure reason; by contract never contains secrets or request URLs (see migration). */
	@Column(name = "error_summary")
	private String errorSummary;

	/** When the run ended, or when it started if it has not recorded an end. */
	public OffsetDateTime lastActivityAt() {
		return finishedAt != null ? finishedAt : startedAt;
	}
}
