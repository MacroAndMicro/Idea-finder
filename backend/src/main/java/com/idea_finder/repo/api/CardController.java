package com.idea_finder.repo.api;

import java.math.BigDecimal;

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

	public CardController(CardQueryService cards) {
		this.cards = cards;
	}

	@GetMapping
	public PageResponse<CardResponse> list(
			@RequestParam(required = false) Integer page,
			@RequestParam(required = false) Integer size,
			@RequestParam(required = false) String q,
			@RequestParam(required = false) String source,
			@RequestParam(required = false) BigDecimal minConfidence,
			@RequestParam(required = false) String intent,
			@RequestParam(required = false) String sort) {
		return cards.list(page, size, q, source, minConfidence, intent, sort);
	}

	@GetMapping("/{id}")
	public CardResponse get(@PathVariable long id) {
		return cards.get(id);
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
