package com.idea_finder.repo.api;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.idea_finder.repo.domain.OpportunityCard;

/**
 * Public shape of an Opportunity Card. Never includes the embedding or the internal
 * reproducibility metadata (llm_model, prompt_version).
 */
public record CardResponse(
		long id,
		String title,
		@JsonProperty("problem_statement") String problemStatement,
		@JsonProperty("trigger_context") String triggerContext,
		@JsonProperty("market_size") String marketSize,
		@JsonProperty("duct_tape_solutions") String ductTapeSolutions,
		@JsonProperty("economic_intent") String economicIntent,
		@JsonProperty("mvp_wedge") String mvpWedge,
		@JsonProperty("confidence_score") BigDecimal confidenceScore,
		@JsonProperty("source_platform") String sourcePlatform,
		@JsonProperty("source_url") String sourceUrl,
		@JsonProperty("raw_content_snippet") String rawContentSnippet,
		@JsonProperty("signal_count") Integer signalCount,
		@JsonProperty("platform_count") Integer platformCount,
		@JsonProperty("first_seen_at") OffsetDateTime firstSeenAt,
		@JsonProperty("last_seen_at") OffsetDateTime lastSeenAt,
		@JsonProperty("created_at") OffsetDateTime createdAt) {

	static CardResponse from(OpportunityCard c) {
		return new CardResponse(
			c.getId(),
			c.getTitle(),
			c.getProblemStatement(),
			c.getTriggerContext(),
			c.getMarketSize(),
			c.getDuctTapeSolutions(),
			c.getEconomicIntent() == null ? null : c.getEconomicIntent().dbValue(),
			c.getMvpWedge(),
			c.getConfidenceScore(),
			c.getSourcePlatform().dbValue(),
			c.getSourceUrl(),
			c.getRawContentSnippet(),
			c.getSignalCount(),
			c.getPlatformCount(),
			c.getFirstSeenAt(),
			c.getLastSeenAt(),
			c.getCreatedAt());
	}
}
