package com.idea_finder.repo.api;

import java.time.Duration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;

/**
 * IF-68: HTTP caching for read-only aggregate endpoints whose data only changes when the daily
 * pipeline runs ({@code /api/stats}, {@code /api/cards/facets}). Only successful responses get the
 * header; error responses keep Spring Security's no-store default. A max-age of 0 disables it.
 */
@Component
public class AggregateCaching {

	private final Duration maxAge;

	public AggregateCaching(@Value("${app.cache.aggregate-max-age:60s}") Duration maxAge) {
		if (maxAge.isNegative()) {
			throw new IllegalArgumentException("app.cache.aggregate-max-age must not be negative");
		}
		this.maxAge = maxAge;
	}

	public <T> ResponseEntity<T> ok(T body) {
		ResponseEntity.BodyBuilder builder = ResponseEntity.ok();
		if (!maxAge.isZero()) {
			builder.cacheControl(CacheControl.maxAge(maxAge).cachePublic());
		}
		return builder.body(body);
	}
}
