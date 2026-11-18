package com.idea_finder.repo.api;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Public liveness endpoint. IF-66: also checks the database, so a probe can tell a live API from
 * one that cannot reach Postgres: 200 {"status":"ok","db":"up"} or 503 {"status":"degraded","db":"down"}.
 * The body never carries error details.
 */
@RestController
@RequestMapping("/api")
public class HealthController {

	private final DatabaseHealthProbe database;

	public HealthController(DatabaseHealthProbe database) {
		this.database = database;
	}

	@GetMapping("/health")
	public ResponseEntity<Map<String, String>> health() {
		boolean up = database.isUp();
		Map<String, String> body = new LinkedHashMap<>();
		body.put("status", up ? "ok" : "degraded");
		body.put("db", up ? "up" : "down");
		return ResponseEntity.status(up ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE)
			.cacheControl(CacheControl.noStore())
			.body(body);
	}
}
