package com.idea_finder.repo.domain;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.repository.Repository;

import jakarta.persistence.criteria.Predicate;

/** Read-only repository: no save/delete methods are exposed. */
public interface OpportunityCardRepository
		extends Repository<OpportunityCard, Long>, JpaSpecificationExecutor<OpportunityCard> {

	java.util.Optional<OpportunityCard> findById(Long id);

	/**
	 * Pageable search. Every filter is optional (null = not filtered).
	 *
	 * @param source        exact source platform
	 * @param minConfidence cards with confidence_score >= this value (null scores excluded)
	 * @param intent        exact economic intent
	 */
	default Page<OpportunityCard> search(SourcePlatform source, BigDecimal minConfidence,
			EconomicIntent intent, Pageable pageable) {
		return findAll(filters(source, minConfidence, intent), pageable);
	}

	static Specification<OpportunityCard> filters(SourcePlatform source, BigDecimal minConfidence,
			EconomicIntent intent) {
		return (root, query, cb) -> {
			List<Predicate> predicates = new ArrayList<>();
			if (source != null) {
				predicates.add(cb.equal(root.get("sourcePlatform"), source));
			}
			if (minConfidence != null) {
				predicates.add(cb.greaterThanOrEqualTo(root.get("confidenceScore"), minConfidence));
			}
			if (intent != null) {
				predicates.add(cb.equal(root.get("economicIntent"), intent));
			}
			return cb.and(predicates.toArray(Predicate[]::new));
		};
	}
}
