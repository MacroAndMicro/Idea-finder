package com.idea_finder.repo.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import org.junit.jupiter.api.Test;

class SourcePlatformConverterTest {

	private final SourcePlatformConverter converter = new SourcePlatformConverter();

	@Test
	void mapsEveryValueToItsDbString() {
		Map<SourcePlatform, String> expected = Map.of(
			SourcePlatform.REDDIT, "reddit",
			SourcePlatform.GITHUB, "github",
			SourcePlatform.HACKERNEWS, "hackernews",
			SourcePlatform.STACKEXCHANGE, "stackexchange",
			SourcePlatform.G2, "g2",
			SourcePlatform.CAPTERRA, "capterra",
			SourcePlatform.OTHER, "other");
		assertThat(expected).hasSize(SourcePlatform.values().length);
		expected.forEach((value, db) -> assertThat(converter.convertToDatabaseColumn(value)).isEqualTo(db));
	}

	@Test
	void roundTripsEveryValue() {
		for (SourcePlatform value : SourcePlatform.values()) {
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
		assertThatThrownBy(() -> converter.convertToEntityAttribute("twitter"))
			.isInstanceOf(IllegalArgumentException.class)
			.hasMessageContaining("Unknown source_platform");
	}

	@Test
	void dbValueMatchingIsCaseSensitive() {
		assertThatThrownBy(() -> converter.convertToEntityAttribute("Reddit"))
			.isInstanceOf(IllegalArgumentException.class);
	}
}
