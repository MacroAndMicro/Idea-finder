package com.idea_finder.repo.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class EconomicIntentConverterTest {

	private final EconomicIntentConverter converter = new EconomicIntentConverter();

	@Test
	void mapsEveryValueToItsDbString() {
		assertThat(converter.convertToDatabaseColumn(EconomicIntent.HIGH)).isEqualTo("High");
		assertThat(converter.convertToDatabaseColumn(EconomicIntent.MEDIUM)).isEqualTo("Medium");
		assertThat(converter.convertToDatabaseColumn(EconomicIntent.LOW)).isEqualTo("Low");
		assertThat(converter.convertToDatabaseColumn(EconomicIntent.UNSPECIFIED)).isEqualTo("Unspecified");
	}

	@Test
	void roundTripsEveryValue() {
		for (EconomicIntent value : EconomicIntent.values()) {
			String db = converter.convertToDatabaseColumn(value);
			assertThat(converter.convertToEntityAttribute(db)).isEqualTo(value);
		}
	}

	@Test
	void nullsStayNull() {
		assertThat(converter.convertToDatabaseColumn(null)).isNull();
		assertThat(converter.convertToEntityAttribute(null)).isNull();
	}

	@Test
	void unknownDbValueThrows() {
		assertThatThrownBy(() -> converter.convertToEntityAttribute("Huge"))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessageContaining("Unknown economic_intent");
	}

	@Test
	void dbValueMatchingIsCaseSensitive() {
		assertThatThrownBy(() -> converter.convertToEntityAttribute("high"))
			.isInstanceOf(IllegalArgumentException.class);
	}
}
