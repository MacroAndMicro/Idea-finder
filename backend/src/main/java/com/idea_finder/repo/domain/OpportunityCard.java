package com.idea_finder.repo.domain;

import java.math.BigDecimal;
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
 * Read-only view of public.opportunity_cards. The table is owned by supabase/migrations;
 * the backend never writes it. The {@code embedding} (pgvector) column is deliberately not
 * mapped so it is never loaded or exposed through the API.
 */
@Entity
@Immutable
@Table(name = "opportunity_cards")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OpportunityCard {

	@Id
	private Long id;

	@Column(name = "title")
	private String title;

	@Convert(converter = SourcePlatformConverter.class)
	@Column(name = "source_platform", nullable = false)
	private SourcePlatform sourcePlatform;

	@Column(name = "source_url")
	private String sourceUrl;

	@Column(name = "raw_content_snippet")
	private String rawContentSnippet;

	@Column(name = "problem_statement", nullable = false)
	private String problemStatement;

	@Column(name = "trigger_context", nullable = false)
	private String triggerContext;

	@Column(name = "market_size")
	private String marketSize;

	@Column(name = "duct_tape_solutions")
	private String ductTapeSolutions;

	@Convert(converter = EconomicIntentConverter.class)
	@Column(name = "economic_intent")
	private EconomicIntent economicIntent;

	@Column(name = "mvp_wedge")
	private String mvpWedge;

	@Column(name = "confidence_score")
	private BigDecimal confidenceScore;

	@Column(name = "status")
	private String status;

	@Column(name = "is_b2b_filtered")
	private Boolean b2bFiltered;

	@Column(name = "embedding_model")
	private String embeddingModel;

	/** IF-35: number of raw signals behind the card (null until card synthesis fills it). */
	@Column(name = "signal_count")
	private Integer signalCount;

	/** IF-35: number of distinct source platforms among the card's signals. */
	@Column(name = "platform_count")
	private Integer platformCount;

	@Column(name = "first_seen_at")
	private OffsetDateTime firstSeenAt;

	@Column(name = "last_seen_at")
	private OffsetDateTime lastSeenAt;

	/** IF-35: internal reproducibility metadata; never exposed by the API. */
	@Column(name = "llm_model")
	private String llmModel;

	/** IF-35: internal reproducibility metadata; never exposed by the API. */
	@Column(name = "prompt_version")
	private String promptVersion;

	@Column(name = "created_at", nullable = false)
	private OffsetDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private OffsetDateTime updatedAt;
}
