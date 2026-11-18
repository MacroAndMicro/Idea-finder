package com.idea_finder.repo.api;

import java.math.BigDecimal;
import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Read-only Opportunity Card API. Tier-based field gating is a future feature. */
@RestController
@RequestMapping("/api/cards")
public class CardController {

	private final CardQueryService cards;
	private final AggregateCaching caching;

	public CardController(CardQueryService cards, AggregateCaching caching) {
		this.cards = cards;
		this.caching = caching;
	}

	@GetMapping
	public PageResponse<CardResponse> list(
			@RequestParam(required = false) Integer page,
			@RequestParam(required = false) Integer size,
			@RequestParam(required = false) String q,
			@RequestParam(required = false) String source,
			@RequestParam(required = false) BigDecimal minConfidence,
			@RequestParam(required = false) String intent,
			@RequestParam(required = false) String sort,
			@RequestParam(required = false) String b2b,
			@RequestParam(required = false) String createdSince) {
		return cards.list(page, size, q, source, minConfidence, intent, sort, b2b, createdSince);
	}

	/** IF-53: counts per filter option for the card list's filter chips (same filters as list). */
	@GetMapping("/facets")
	public ResponseEntity<FacetsResponse> facets(
			@RequestParam(required = false) String q,
			@RequestParam(required = false) String source,
			@RequestParam(required = false) BigDecimal minConfidence,
			@RequestParam(required = false) String intent,
			@RequestParam(required = false) String b2b,
			@RequestParam(required = false) String createdSince) {
		// IF-68: cacheable like /api/stats; card list, detail, signals and similar stay uncached.
		return caching.ok(cards.facets(q, source, minConfidence, intent, b2b, createdSince));
	}

	@GetMapping("/{id}")
	public CardResponse get(@PathVariable long id) {
		return cards.get(id);
	}

	/** IF-24: related cards (nearest by embedding), most similar first. */
	@GetMapping("/{id}/similar")
	public List<SimilarCardResponse> similar(
			@PathVariable long id,
			@RequestParam(required = false) Integer limit) {
		return cards.similar(id, limit);
	}

	/** The raw signals (evidence) a card is anchored in. */
	@GetMapping("/{id}/signals")
	public PageResponse<SignalResponse> signals(
			@PathVariable long id,
			@RequestParam(required = false) Integer page,
			@RequestParam(required = false) Integer size) {
		return cards.signals(id, page, size);
	}
}
