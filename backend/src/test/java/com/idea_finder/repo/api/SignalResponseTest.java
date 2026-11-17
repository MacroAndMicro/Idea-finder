package com.idea_finder.repo.api;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class SignalResponseTest {

	@Test
	void shortAndNullBodiesAreUnchanged() {
		assertThat(SignalResponse.snippet(null)).isNull();
		assertThat(SignalResponse.snippet("abc")).isEqualTo("abc");
		assertThat(SignalResponse.snippet("y".repeat(500))).hasSize(500);
	}

	@Test
	void truncatesWithoutSplittingSurrogatePairs() {
		String emoji = "😀"; // one code point, two chars
		String body = emoji.repeat(501);
		String snippet = SignalResponse.snippet(body);
		assertThat(snippet.codePointCount(0, snippet.length())).isEqualTo(500);
		assertThat(Character.isHighSurrogate(snippet.charAt(snippet.length() - 1))).isFalse();
	}
}
