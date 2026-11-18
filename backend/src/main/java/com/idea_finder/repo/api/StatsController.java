package com.idea_finder.repo.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Public read-only ingestion stats (IF-18). */
@RestController
@RequestMapping("/api/stats")
public class StatsController {

	private final StatsService stats;
	private final AggregateCaching caching;

	public StatsController(StatsService stats, AggregateCaching caching) {
		this.stats = stats;
		this.caching = caching;
	}

	/** IF-68: cacheable for app.cache.aggregate-max-age (data changes only when the pipeline runs). */
	@GetMapping
	public ResponseEntity<StatsResponse> get() {
		return caching.ok(stats.stats());
	}
}
