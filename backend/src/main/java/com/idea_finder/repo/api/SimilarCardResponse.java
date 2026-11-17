package com.idea_finder.repo.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonUnwrapped;

/** A {@link CardResponse} plus its similarity (0..1, higher is closer) to the requested card. */
public record SimilarCardResponse(
		@JsonUnwrapped CardResponse card,
		@JsonProperty("similarity") double similarity) {

	/**
	 * Cosine similarity (1 - cosine distance), clamped to 0..1 (opposite vectors count as unrelated)
	 * and rounded to 4 decimals. pgvector returns NaN for a zero vector; that counts as 0.
	 */
	static SimilarCardResponse of(CardResponse card, double cosineDistance) {
		if (Double.isNaN(cosineDistance)) {
			return new SimilarCardResponse(card, 0.0);
		}
		double similarity = Math.max(0.0, Math.min(1.0, 1.0 - cosineDistance));
		return new SimilarCardResponse(card, Math.round(similarity * 10_000) / 10_000.0);
	}
}
