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
 * Counts and {@code error_summary} are deliberately not mapped: the API only exposes
 * when each source last ran and how that run ended.
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

	/** When the run ended, or when it started if it has not recorded an end. */
	public OffsetDateTime lastActivityAt() {
		return finishedAt != null ? finishedAt : startedAt;
	}
}
