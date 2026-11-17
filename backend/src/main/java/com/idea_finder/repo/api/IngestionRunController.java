package com.idea_finder.repo.api;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** IF-36: read-only recent ingestion run history, newest first. */
@RestController
@RequestMapping("/api/ingestion-runs")
public class IngestionRunController {

	private final IngestionRunService runs;

	public IngestionRunController(IngestionRunService runs) {
		this.runs = runs;
	}

	@GetMapping
	public PageResponse<IngestionRunResponse> list(
			@RequestParam(required = false) Integer page,
			@RequestParam(required = false) Integer size,
			@RequestParam(required = false) String source,
			@RequestParam(required = false) String status) {
		return runs.list(page, size, source, status);
	}
}
