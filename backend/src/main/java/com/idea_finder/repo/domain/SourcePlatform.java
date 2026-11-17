package com.idea_finder.repo.domain;

import java.util.Arrays;

/** Allowed values of opportunity_cards.source_platform (enforced by a CHECK constraint). */
public enum SourcePlatform {
	REDDIT("reddit"),
	GITHUB("github"),
	HACKERNEWS("hackernews"),
	STACKEXCHANGE("stackexchange"),
	G2("g2"),
	CAPTERRA("capterra"),
	OTHER("other");

	private final String dbValue;

	SourcePlatform(String dbValue) {
		this.dbValue = dbValue;
	}

	/** The value stored in the database and used in the API. */
	public String dbValue() {
		return dbValue;
	}

	public static SourcePlatform fromDbValue(String value) {
		return Arrays.stream(values())
			.filter(p -> p.dbValue.equals(value))
			.findFirst()
			.orElseThrow(() -> new IllegalArgumentException("Unknown source_platform: " + value));
	}
}
