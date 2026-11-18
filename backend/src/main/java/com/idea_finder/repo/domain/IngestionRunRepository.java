package com.idea_finder.repo.domain;

import java.util.ArrayList;
import java.util.List;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;

import jakarta.persistence.criteria.Predicate;

/** Read-only repository: no save/delete methods are exposed. */
public interface IngestionRunRepository
		extends Repository<IngestionRun, Long>, JpaSpecificationExecutor<IngestionRun> {

	/** IF-36: run history, optionally filtered by exact source and/or status (null = not filtered). */
	default Page<IngestionRun> search(SourcePlatform source, String status, Pageable pageable) {
		return findAll(filters(source, status), pageable);
	}

	static Specification<IngestionRun> filters(SourcePlatform source, String status) {
		return (root, query, cb) -> {
			List<Predicate> predicates = new ArrayList<>();
			if (source != null) {
				predicates.add(cb.equal(root.get("sourcePlatform"), source));
			}
			if (status != null) {
				predicates.add(cb.equal(root.get("status"), status));
			}
			return cb.and(predicates.toArray(Predicate[]::new));
		};
	}

	/**
	 * The most recently started run of every source (served by ingestion_runs_source_started_idx).
	 * Two runs with the same started_at can both be returned; callers keep the higher id.
	 */
	@Query("""
		select r from IngestionRun r
		where r.startedAt = (select max(r2.startedAt) from IngestionRun r2 where r2.sourcePlatform = r.sourcePlatform)
		""")
	List<IngestionRun> findLatestPerSource();
}
