package com.idea_finder.repo.api;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.Locale;
import java.util.stream.Collectors;

import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.domain.EconomicIntent;
import com.idea_finder.repo.domain.OpportunityCard;
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
	public static final int MIN_Q = 2;
	public static final int MAX_Q = 100;
	public static final int DEFAULT_SIMILAR = 5;
	public static final int MAX_SIMILAR = 20;

	private final OpportunityCardRepository repository;
	private final RawSignalRepository signals;

	public CardQueryService(OpportunityCardRepository repository, RawSignalRepository signals) {
		this.repository = repository;
		this.signals = signals;
	}

	public PageResponse<CardResponse> list(Integer page, Integer size, String source,
			BigDecimal minConfidence, String intent, String sort) {
		return list(page, size, null, source, minConfidence, intent, sort);
	}

	public PageResponse<CardResponse> list(Integer page, Integer size, String q, String source,
			BigDecimal minConfidence, String intent, String sort) {
		return list(page, size, q, source, minConfidence, intent, sort, null);
	}

	public PageResponse<CardResponse> list(Integer page, Integer size, String q, String source,
			BigDecimal minConfidence, String intent, String sort, String b2b) {
		String keyword = parseQuery(q);
		checkMinConfidence(minConfidence);
		PageRequest pageable = pageRequest(page, size, parseSort(sort));
		return PageResponse.of(
			repository.search(keyword, parseSource(source), minConfidence, parseIntent(intent), parseB2b(b2b),
				pageable),
			CardResponse::from);
	}

	/**
	 * IF-53: card counts per source_platform, economic_intent and is_b2b_filtered for the filter
	 * chips. Takes the same filters as {@link #list}; each facet applies every filter except its own,
	 * so the counts say how many cards selecting that option would return. Cards whose value is
	 * null (unknown intent / B2B flag) are counted in {@code total} but in no bucket.
	 */
	public FacetsResponse facets(String q, String source, BigDecimal minConfidence, String intent, String b2b) {
		String keyword = parseQuery(q);
		SourcePlatform platform = parseSource(source);
		checkMinConfidence(minConfidence);
		EconomicIntent economicIntent = parseIntent(intent);
		Boolean b2bFlag = parseB2b(b2b);
		return FacetsResponse.of(
			repository.count(OpportunityCardRepository.filters(keyword, platform, minConfidence, economicIntent, b2bFlag)),
			repository.countGroupedBy("sourcePlatform",
				OpportunityCardRepository.filters(keyword, null, minConfidence, economicIntent, b2bFlag)),
			repository.countGroupedBy("economicIntent",
				OpportunityCardRepository.filters(keyword, platform, minConfidence, null, b2bFlag)),
			repository.countGroupedBy("b2bFiltered",
				OpportunityCardRepository.filters(keyword, platform, minConfidence, economicIntent, null)));
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

	/**
	 * IF-24: cards nearest to {@code id} by embedding (cosine), most similar first. 404 for an
	 * unknown card; empty when the card has no embedding.
	 */
	public List<SimilarCardResponse> similar(long id, Integer limit) {
		int n = limit == null ? DEFAULT_SIMILAR : limit;
		if (n < 1 || n > MAX_SIMILAR) {
			throw new InvalidParameterException("limit", "limit must be between 1 and " + MAX_SIMILAR);
		}
		if (!repository.existsById(id)) {
			throw new CardNotFoundException(id);
		}
		List<Object[]> nearest = repository.findNearest(id, n);
		if (nearest.isEmpty()) {
			return List.of();
		}
		Map<Long, OpportunityCard> byId = repository
			.findByIdIn(nearest.stream().map(row -> ((Number) row[0]).longValue()).toList())
			.stream()
			.collect(Collectors.toMap(OpportunityCard::getId, Function.identity()));
		List<SimilarCardResponse> result = new ArrayList<>(nearest.size());
		for (Object[] row : nearest) {
			OpportunityCard card = byId.get(((Number) row[0]).longValue());
			if (card != null) { // deleted between the two queries
				result.add(SimilarCardResponse.of(CardResponse.from(card), ((Number) row[1]).doubleValue()));
			}
		}
		return result;
	}

	/** Shared paging limits for every list endpoint. */
	static PageRequest pageRequest(Integer page, Integer size, Sort sort) {
		return pageRequest(page, size, sort, MAX_SIZE);
	}

	/** As {@link #pageRequest(Integer, Integer, Sort)} with an endpoint-specific maximum size. */
	static PageRequest pageRequest(Integer page, Integer size, Sort sort, int maxSize) {
		int p = page == null ? 0 : page;
		int s = size == null ? DEFAULT_SIZE : size;
		if (p < 0 || p > MAX_PAGE) {
			throw new InvalidParameterException("page", "page must be between 0 and " + MAX_PAGE);
		}
		if (s < 1 || s > maxSize) {
			throw new InvalidParameterException("size", "size must be between 1 and " + maxSize);
		}
		return PageRequest.of(p, s, sort);
	}

	/** Trimmed keyword, or null when absent/blank; length is bounded to keep LIKE scans cheap. */
	static String parseQuery(String q) {
		if (isBlank(q)) {
			return null;
		}
		String value = q.trim();
		int length = value.codePointCount(0, value.length());
		if (length < MIN_Q || length > MAX_Q) {
			throw new InvalidParameterException("q", "q must be between " + MIN_Q + " and " + MAX_Q + " characters");
		}
		return value;
	}

	static Sort parseSort(String sort) {
		String value = isBlank(sort) ? "confidence" : sort.trim().toLowerCase(Locale.ROOT);
		Sort newest = Sort.by(Sort.Order.desc("createdAt"), Sort.Order.desc("id"));
		return switch (value) {
			case "confidence" -> Sort.by(Sort.Order.desc("confidenceScore").nullsLast()).and(newest);
			case "newest" -> newest;
			// IF-35: most recently seen in the sources first; cards without signal dates last.
			case "recent" -> Sort.by(Sort.Order.desc("lastSeenAt").nullsLast(), Sort.Order.desc("id"));
			default -> throw new InvalidParameterException("sort", "sort must be one of: confidence, newest, recent");
		};
	}

	static void checkMinConfidence(BigDecimal minConfidence) {
		if (minConfidence != null
				&& (minConfidence.compareTo(BigDecimal.ZERO) < 0 || minConfidence.compareTo(BigDecimal.valueOf(100)) > 0)) {
			throw new InvalidParameterException("minConfidence", "minConfidence must be between 0 and 100");
		}
	}

	/** IF-37: strict true/false (case-insensitive); absent/blank = no filter. */
	static Boolean parseB2b(String b2b) {
		if (isBlank(b2b)) {
			return null;
		}
		return switch (b2b.trim().toLowerCase(Locale.ROOT)) {
			case "true" -> Boolean.TRUE;
			case "false" -> Boolean.FALSE;
			default -> throw new InvalidParameterException("b2b", "b2b must be true or false");
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
