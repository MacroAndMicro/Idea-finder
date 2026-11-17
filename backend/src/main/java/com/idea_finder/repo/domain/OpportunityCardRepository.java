package com.idea_finder.repo.domain;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.repository.Repository;

import jakarta.persistence.criteria.Predicate;

/** Read-only repository: no save/delete methods are exposed. */
public interface OpportunityCardRepository
		extends Repository<OpportunityCard, Long>, JpaSpecificationExecutor<OpportunityCard> {

	java.util.Optional<OpportunityCard> findById(Long id);

	boolean existsById(Long id);

	long count();

	/** Rows of [SourcePlatform, Long count]. */
	@Query("select c.sourcePlatform, count(c) from OpportunityCard c group by c.sourcePlatform")
	List<Object[]> countBySource();

	/**
	 * Pageable search. Every filter is optional (null = not filtered).
	 *
	 * @param source        exact source platform
	 * @param minConfidence cards with confidence_score >= this value (null scores excluded)
	 * @param intent        exact economic intent
	 */
	default Page<OpportunityCard> search(SourcePlatform source, BigDecimal minConfidence,
			EconomicIntent intent, Pageable pageable) {
		return search(null, source, minConfidence, intent, pageable);
	}

	/**
	 * As {@link #search(SourcePlatform, BigDecimal, EconomicIntent, Pageable)}, plus an optional
	 * case-insensitive keyword {@code q} matched as a literal substring of title, problem_statement
	 * or duct_tape_solutions. The value is bound as a parameter and its LIKE wildcards are escaped.
	 */
	default Page<OpportunityCard> search(String q, SourcePlatform source, BigDecimal minConfidence,
			EconomicIntent intent, Pageable pageable) {
		return findAll(filters(q, source, minConfidence, intent), pageable);
	}

	char LIKE_ESCAPE = '\\';

	/** Escapes LIKE metacharacters so user input only ever matches literally. */
	static String likeContains(String q) {
		String escaped = q.toLowerCase(Locale.ROOT)
			.replace("\\", "\\\\")
			.replace("%", "\\%")
			.replace("_", "\\_");
		return "%" + escaped + "%";
	}

	static Specification<OpportunityCard> filters(String q, SourcePlatform source, BigDecimal minConfidence,
			EconomicIntent intent) {
		return (root, query, cb) -> {
			List<Predicate> predicates = new ArrayList<>();
			if (q != null) {
				String pattern = likeContains(q);
				predicates.add(cb.or(
					cb.like(cb.lower(root.get("title")), pattern, LIKE_ESCAPE),
					cb.like(cb.lower(root.get("problemStatement")), pattern, LIKE_ESCAPE),
					cb.like(cb.lower(root.get("ductTapeSolutions")), pattern, LIKE_ESCAPE)));
			}
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
