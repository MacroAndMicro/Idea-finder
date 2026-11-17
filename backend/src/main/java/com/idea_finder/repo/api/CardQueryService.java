package com.idea_finder.repo.api;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Locale;
import java.util.stream.Collectors;

import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.domain.EconomicIntent;
import com.idea_finder.repo.domain.OpportunityCardRepository;
import com.idea_finder.repo.domain.RawSignalRepository;
import com.idea_finder.repo.domain.SourcePlatform;

/** Validates card list parameters and runs read-only queries. */
@Service
@Transactional(readOnly = true)
public class CardQueryService {

	public static final int DEFAULT_SIZE = 20;
	public static final int MAX_SIZE = 50;
	/** Guards against huge OFFSETs (page * size) hitting the database. */
	public static final int MAX_PAGE = 10_000;

	private final OpportunityCardRepository repository;
	private final RawSignalRepository signals;

	public CardQueryService(OpportunityCardRepository repository, RawSignalRepository signals) {
		this.repository = repository;
		this.signals = signals;
	}

	public PageResponse<CardResponse> list(Integer page, Integer size, String source,
			BigDecimal minConfidence, String intent, String sort) {
		if (minConfidence != null
				&& (minConfidence.compareTo(BigDecimal.ZERO) < 0 || minConfidence.compareTo(BigDecimal.valueOf(100)) > 0)) {
			throw new InvalidParameterException("minConfidence", "minConfidence must be between 0 and 100");
		}
		PageRequest pageable = pageRequest(page, size, parseSort(sort));
		return PageResponse.of(
			repository.search(parseSource(source), minConfidence, parseIntent(intent), pageable),
			CardResponse::from);
	}

	public CardResponse get(long id) {
		return repository.findById(id).map(CardResponse::from).orElseThrow(() -> new CardNotFoundException(id));
	}

	/** Evidence behind a card: its linked raw signals, newest source post first. */
	public PageResponse<SignalResponse> signals(long cardId, Integer page, Integer size) {
		PageRequest pageable = pageRequest(page, size,
			Sort.by(Sort.Order.desc("sourceCreatedAt").nullsLast(), Sort.Order.desc("id")));
		if (!repository.existsById(cardId)) {
			throw new CardNotFoundException(cardId);
		}
		return PageResponse.of(signals.findByCardId(cardId, pageable), SignalResponse::from);
	}

	/** Shared paging limits for every list endpoint. */
	static PageRequest pageRequest(Integer page, Integer size, Sort sort) {
		int p = page == null ? 0 : page;
		int s = size == null ? DEFAULT_SIZE : size;
		if (p < 0 || p > MAX_PAGE) {
			throw new InvalidParameterException("page", "page must be between 0 and " + MAX_PAGE);
		}
		if (s < 1 || s > MAX_SIZE) {
			throw new InvalidParameterException("size", "size must be between 1 and " + MAX_SIZE);
		}
		return PageRequest.of(p, s, sort);
	}

	static Sort parseSort(String sort) {
		String value = isBlank(sort) ? "confidence" : sort.trim().toLowerCase(Locale.ROOT);
		Sort newest = Sort.by(Sort.Order.desc("createdAt"), Sort.Order.desc("id"));
		return switch (value) {
			case "confidence" -> Sort.by(Sort.Order.desc("confidenceScore").nullsLast()).and(newest);
			case "newest" -> newest;
			default -> throw new InvalidParameterException("sort", "sort must be one of: confidence, newest");
		};
	}

	static SourcePlatform parseSource(String source) {
		if (isBlank(source)) {
			return null;
		}
		String value = source.trim().toLowerCase(Locale.ROOT);
		return Arrays.stream(SourcePlatform.values())
			.filter(p -> p.dbValue().equals(value))
			.findFirst()
			.orElseThrow(() -> new InvalidParameterException("source", "source must be one of: "
				+ Arrays.stream(SourcePlatform.values()).map(SourcePlatform::dbValue).collect(Collectors.joining(", "))));
	}

	static EconomicIntent parseIntent(String intent) {
		if (isBlank(intent)) {
			return null;
		}
		String value = intent.trim();
		return Arrays.stream(EconomicIntent.values())
			.filter(i -> i.dbValue().equalsIgnoreCase(value))
			.findFirst()
			.orElseThrow(() -> new InvalidParameterException("intent", "intent must be one of: "
				+ Arrays.stream(EconomicIntent.values()).map(EconomicIntent::dbValue).collect(Collectors.joining(", "))));
	}

	private static boolean isBlank(String s) {
		return s == null || s.isBlank();
	}
}
