package com.idea_finder.repo.domain;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import jakarta.persistence.criteria.Predicate;

/** Read-only repository: no save/delete methods are exposed. */
public interface OpportunityCardRepository
		extends Repository<OpportunityCard, Long>, JpaSpecificationExecutor<OpportunityCard> {

	java.util.Optional<OpportunityCard> findById(Long id);

	boolean existsById(Long id);

	long count();

	List<OpportunityCard> findByIdIn(Collection<Long> ids);

	/**
	 * IF-24: rows of [Long id, Double cosineDistance] of the cards nearest to {@code id} by embedding,
	 * nearest first, excluding the card itself and cards without an embedding. Empty when the card
	 * has no embedding. The distance expression matches the HNSW (vector_cosine_ops) index, and the
	 * target vector is an uncorrelated subquery so the planner can use that index (approximate
	 * nearest-neighbour; no secondary sort key, which would force a full scan).
	 */
	@Query(nativeQuery = true, value = """
		select c.id, c.embedding <=> (select t.embedding from {h-schema}opportunity_cards t where t.id = :id) as distance
		from {h-schema}opportunity_cards c
		where c.id <> :id
		  and c.embedding is not null
		  and exists (select 1 from {h-schema}opportunity_cards t where t.id = :id and t.embedding is not null)
		order by c.embedding <=> (select t.embedding from {h-schema}opportunity_cards t where t.id = :id)
		limit :limit
		""")
	List<Object[]> findNearest(@Param("id") long id, @Param("limit") int limit);

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
		return search(q, source, minConfidence, intent, null, pageable);
	}

	/**
	 * As above, plus IF-37's optional {@code b2b} filter on is_b2b_filtered: true/false match that
	 * exact value (cards with an unknown/null flag match neither); null = not filtered.
	 */
	default Page<OpportunityCard> search(String q, SourcePlatform source, BigDecimal minConfidence,
			EconomicIntent intent, Boolean b2b, Pageable pageable) {
		return findAll(filters(q, source, minConfidence, intent, b2b), pageable);
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
			EconomicIntent intent, Boolean b2b) {
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
			if (b2b != null) {
				predicates.add(cb.equal(root.get("b2bFiltered"), b2b));
			}
			return cb.and(predicates.toArray(Predicate[]::new));
		};
	}
}
