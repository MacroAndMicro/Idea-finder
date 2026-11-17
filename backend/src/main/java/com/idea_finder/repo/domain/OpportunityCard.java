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

	@Column(name = "created_at", nullable = false)
	private OffsetDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private OffsetDateTime updatedAt;
}
