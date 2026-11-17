package com.idea_finder.repo.domain;

import java.util.Arrays;

/** Allowed values of opportunity_cards.economic_intent (enforced by a CHECK constraint). */
public enum EconomicIntent {
	HIGH("High"),
	MEDIUM("Medium"),
	LOW("Low"),
	UNSPECIFIED("Unspecified");

	private final String dbValue;

	EconomicIntent(String dbValue) {
		this.dbValue = dbValue;
	}

	/** The value stored in the database and used in the API. */
	public String dbValue() {
		return dbValue;
	}

	public static EconomicIntent fromDbValue(String value) {
		return Arrays.stream(values())
			.filter(i -> i.dbValue.equals(value))
			.findFirst()
			.orElseThrow(() -> new IllegalArgumentException("Unknown economic_intent: " + value));
	}
}
