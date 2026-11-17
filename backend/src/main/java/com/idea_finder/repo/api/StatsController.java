package com.idea_finder.repo.api;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Public read-only ingestion stats (IF-18). */
@RestController
@RequestMapping("/api/stats")
public class StatsController {

	private final StatsService stats;

	public StatsController(StatsService stats) {
		this.stats = stats;
	}

	@GetMapping
	public StatsResponse get() {
		return stats.stats();
	}
}
