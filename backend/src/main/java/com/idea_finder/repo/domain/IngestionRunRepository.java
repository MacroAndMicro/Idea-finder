package com.idea_finder.repo.domain;

import java.util.List;

import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;

/** Read-only repository: no save/delete methods are exposed. */
public interface IngestionRunRepository extends Repository<IngestionRun, Long> {

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
