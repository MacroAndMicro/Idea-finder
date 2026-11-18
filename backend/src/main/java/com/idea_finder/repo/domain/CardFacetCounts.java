package com.idea_finder.repo.domain;

import java.util.List;

import org.springframework.data.jpa.domain.Specification;

/** IF-53: GROUP BY counts over opportunity_cards, computed in SQL (no card rows are loaded). */
public interface CardFacetCounts {

	/**
	 * Rows of [attribute value, Long count] for the cards matching {@code spec}, grouped by the
	 * entity attribute {@code attribute}. The attribute name is supplied by code, never by clients.
	 */
	List<Object[]> countGroupedBy(String attribute, Specification<OpportunityCard> spec);
}
