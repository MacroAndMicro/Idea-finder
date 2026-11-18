package com.idea_finder.repo.config;

import java.util.Comparator;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongSupplier;

/**
 * IF-67: in-memory token bucket per client key. Each bucket holds up to {@code perMinute} tokens and
 * refills continuously at {@code perMinute / 60s}. Memory is bounded: buckets idle for a full refill
 * window are evicted (a fresh bucket is identical to a full one), and above {@code maxClients} the
 * least recently seen buckets are dropped.
 */
public class RateLimiter {

	private static final long WINDOW_NANOS = 60_000_000_000L;

	/** Outcome of one request: allowed, or denied with the seconds until a token is available. */
	public record Decision(boolean allowed, long retryAfterSeconds) {
	}

	private final int perMinute;
	private final int maxClients;
	private final double tokensPerNano;
	private final LongSupplier nanoClock;
	private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

	public RateLimiter(int perMinute, int maxClients, LongSupplier nanoClock) {
		if (perMinute < 1) {
			throw new IllegalArgumentException("rate limit per minute must be >= 1");
		}
		if (maxClients < 1) {
			throw new IllegalArgumentException("rate limit max clients must be >= 1");
		}
		this.perMinute = perMinute;
		this.maxClients = maxClients;
		this.tokensPerNano = perMinute / (double) WINDOW_NANOS;
		this.nanoClock = nanoClock;
	}

	public Decision tryAcquire(String client) {
		long now = nanoClock.getAsLong();
		if (buckets.size() >= maxClients && !buckets.containsKey(client)) {
			evict(now);
		}
		Bucket bucket = buckets.computeIfAbsent(client, k -> new Bucket(perMinute, now));
		return bucket.take(now);
	}

	int trackedClients() {
		return buckets.size();
	}

	/** Drop idle buckets; if still at the cap, drop the least recently seen ones down to 90 %. */
	private synchronized void evict(long now) {
		buckets.values().removeIf(b -> now - b.lastSeen >= WINDOW_NANOS);
		int target = Math.max(0, (int) (maxClients * 0.9) - 1);
		if (buckets.size() > target) {
			buckets.entrySet().stream()
				.sorted(Comparator.comparingLong(e -> e.getValue().lastSeen))
				.limit(buckets.size() - target)
				.map(Map.Entry::getKey)
				.toList()
				.forEach(buckets::remove);
		}
	}

	private final class Bucket {

		private double tokens;
		private long lastRefill;
		private volatile long lastSeen;

		Bucket(int capacity, long now) {
			this.tokens = capacity;
			this.lastRefill = now;
			this.lastSeen = now;
		}

		synchronized Decision take(long now) {
			long elapsed = Math.max(0, now - lastRefill);
			tokens = Math.min(perMinute, tokens + elapsed * tokensPerNano);
			lastRefill = now;
			lastSeen = now;
			if (tokens >= 1) {
				tokens -= 1;
				return new Decision(true, 0);
			}
			double missingNanos = (1 - tokens) / tokensPerNano;
			long seconds = (long) Math.ceil(missingNanos / 1_000_000_000d);
			return new Decision(false, Math.max(1, seconds));
		}
	}
}
