package com.idea_finder.repo.api;

import java.util.List;
import java.util.Locale;

import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.domain.IngestionRunRepository;

/** IF-36: validates parameters and reads the ingestion run history. */
@Service
@Transactional(readOnly = true)
public class IngestionRunService {

	public static final int MAX_SIZE = 100;
	/** Mirrors the ingestion_runs_status_chk constraint. */
	static final List<String> STATUSES = List.of("Success", "Partial", "Failed");

	private static final Sort NEWEST_FIRST = Sort.by(Sort.Order.desc("startedAt"), Sort.Order.desc("id"));

	private final IngestionRunRepository runs;

	public IngestionRunService(IngestionRunRepository runs) {
		this.runs = runs;
	}

	public PageResponse<IngestionRunResponse> list(Integer page, Integer size, String source, String status) {
		return PageResponse.of(
			runs.search(CardQueryService.parseSource(source), parseStatus(status),
				CardQueryService.pageRequest(page, size, NEWEST_FIRST, MAX_SIZE)),
			IngestionRunResponse::from);
	}

	/** Case-insensitive match to the canonical Success/Partial/Failed; blank = no filter. */
	static String parseStatus(String status) {
		if (status == null || status.isBlank()) {
			return null;
		}
		String value = status.trim().toLowerCase(Locale.ROOT);
		return STATUSES.stream()
			.filter(s -> s.toLowerCase(Locale.ROOT).equals(value))
			.findFirst()
			.orElseThrow(() -> new InvalidParameterException("status",
				"status must be one of: " + String.join(", ", STATUSES)));
	}
}
