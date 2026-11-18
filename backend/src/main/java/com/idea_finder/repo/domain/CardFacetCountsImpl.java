package com.idea_finder.repo.domain;

import java.util.List;
import java.util.Set;

import org.springframework.data.jpa.domain.Specification;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Path;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;

/** Spring Data fragment implementation for {@link CardFacetCounts}. */
class CardFacetCountsImpl implements CardFacetCounts {

	/** Defence in depth: only these attributes may be grouped on. */
	static final Set<String> FACET_ATTRIBUTES = Set.of("sourcePlatform", "economicIntent", "b2bFiltered");

	@PersistenceContext
	private EntityManager em;

	@Override
	public List<Object[]> countGroupedBy(String attribute, Specification<OpportunityCard> spec) {
		if (!FACET_ATTRIBUTES.contains(attribute)) {
			throw new IllegalArgumentException("Not a facet attribute: " + attribute);
		}
		CriteriaBuilder cb = em.getCriteriaBuilder();
		CriteriaQuery<Object[]> query = cb.createQuery(Object[].class);
		Root<OpportunityCard> root = query.from(OpportunityCard.class);
		Path<Object> key = root.get(attribute);
		query.multiselect(key, cb.count(root));
		Predicate where = spec.toPredicate(root, query, cb);
		if (where != null) {
			query.where(where);
		}
		query.groupBy(key);
		return em.createQuery(query).getResultList();
	}
}
