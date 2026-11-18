package com.idea_finder.repo.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.concurrent.atomic.AtomicLong;

import org.junit.jupiter.api.Test;

/** IF-67: token bucket math, refill, Retry-After and bounded memory. */
class RateLimiterTest {

	static final long SECOND = 1_000_000_000L;

	final AtomicLong clock = new AtomicLong(0);

	@Test
	void allowsUpToLimitThenDenies() {
		RateLimiter limiter = new RateLimiter(3, 100, clock::get);
		assertThat(limiter.tryAcquire("a").allowed()).isTrue();
		assertThat(limiter.tryAcquire("a").allowed()).isTrue();
		assertThat(limiter.tryAcquire("a").allowed()).isTrue();
		RateLimiter.Decision denied = limiter.tryAcquire("a");
		assertThat(denied.allowed()).isFalse();
		// 3/min = one token every 20 s
		assertThat(denied.retryAfterSeconds()).isEqualTo(20);
		// other clients have their own bucket
		assertThat(limiter.tryAcquire("b").allowed()).isTrue();
	}

	@Test
	void refillsOverTime() {
		RateLimiter limiter = new RateLimiter(60, 100, clock::get);
		for (int i = 0; i < 60; i++) {
			assertThat(limiter.tryAcquire("a").allowed()).isTrue();
		}
		assertThat(limiter.tryAcquire("a").allowed()).isFalse();
		clock.addAndGet(SECOND / 2);
		RateLimiter.Decision half = limiter.tryAcquire("a");
		assertThat(half.allowed()).isFalse();
		assertThat(half.retryAfterSeconds()).isEqualTo(1);
		clock.addAndGet(SECOND);
		assertThat(limiter.tryAcquire("a").allowed()).isTrue();
	}

	@Test
	void neverExceedsCapacityAfterLongIdle() {
		RateLimiter limiter = new RateLimiter(2, 100, clock::get);
		clock.addAndGet(3600 * SECOND);
		assertThat(limiter.tryAcquire("a").allowed()).isTrue();
		assertThat(limiter.tryAcquire("a").allowed()).isTrue();
		assertThat(limiter.tryAcquire("a").allowed()).isFalse();
	}

	@Test
	void memoryIsBounded() {
		RateLimiter limiter = new RateLimiter(10, 50, clock::get);
		for (int i = 0; i < 1000; i++) {
			clock.addAndGet(1000);
			limiter.tryAcquire("client-" + i);
		}
		assertThat(limiter.trackedClients()).isLessThanOrEqualTo(50);
	}

	@Test
	void idleClientsAreEvictedFirst() {
		RateLimiter limiter = new RateLimiter(10, 3, clock::get);
		limiter.tryAcquire("old");
		clock.addAndGet(61 * SECOND);
		limiter.tryAcquire("b");
		limiter.tryAcquire("c");
		limiter.tryAcquire("d");
		assertThat(limiter.trackedClients()).isLessThanOrEqualTo(3);
	}

	@Test
	void rejectsInvalidConfig() {
		assertThatThrownBy(() -> new RateLimiter(0, 10, clock::get)).isInstanceOf(IllegalArgumentException.class);
		assertThatThrownBy(() -> new RateLimiter(10, 0, clock::get)).isInstanceOf(IllegalArgumentException.class);
	}
}
