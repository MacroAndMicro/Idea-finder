package com.idea_finder.repo.api;

import java.time.OffsetDateTime;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.idea_finder.repo.domain.RawSignal;

/** Public shape of a raw signal backing a card. Never includes author or content hashes. */
public record SignalResponse(
		long id,
		@JsonProperty("source_platform") String sourcePlatform,
		String url,
		String title,
		@JsonProperty("body_snippet") String bodySnippet,
		Integer score,
		@JsonProperty("comment_count") Integer commentCount,
		@JsonProperty("source_created_at") OffsetDateTime sourceCreatedAt) {

	public static final int MAX_SNIPPET_CHARS = 500;

	static SignalResponse from(RawSignal s) {
		return new SignalResponse(
			s.getId(),
			s.getSourcePlatform().dbValue(),
			s.getUrl(),
			s.getTitle(),
			snippet(s.getBody()),
			s.getScore(),
			s.getCommentCount(),
			s.getSourceCreatedAt());
	}

	/** First {@value #MAX_SNIPPET_CHARS} code points, never splitting a surrogate pair. */
	static String snippet(String body) {
		if (body == null || body.codePointCount(0, body.length()) <= MAX_SNIPPET_CHARS) {
			return body;
		}
		return body.substring(0, body.offsetByCodePoints(0, MAX_SNIPPET_CHARS));
	}
}
