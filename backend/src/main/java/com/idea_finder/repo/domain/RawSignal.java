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
 * Read-only view of public.raw_signals (written only by the ingestion pipeline).
 * {@code author_handle_hash}, {@code content_hash} and {@code tags} are deliberately not mapped,
 * so they can never be loaded or exposed through the API.
 */
@Entity
@Immutable
@Table(name = "raw_signals")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RawSignal {

	@Id
	private Long id;

	@Convert(converter = SourcePlatformConverter.class)
	@Column(name = "source_platform", nullable = false)
	private SourcePlatform sourcePlatform;

	@Column(name = "url", nullable = false)
	private String url;

	@Column(name = "title")
	private String title;

	@Column(name = "body")
	private String body;

	@Column(name = "score")
	private Integer score;

	@Column(name = "comment_count")
	private Integer commentCount;

	@Column(name = "source_created_at")
	private OffsetDateTime sourceCreatedAt;

	@Column(name = "fetched_at", nullable = false)
	private OffsetDateTime fetchedAt;

	@Column(name = "processed_at")
	private OffsetDateTime processedAt;
}
