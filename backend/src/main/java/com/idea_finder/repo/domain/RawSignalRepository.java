package com.idea_finder.repo.domain;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/** Read-only repository: no save/delete methods are exposed. */
public interface RawSignalRepository extends Repository<RawSignal, Long> {

	/** Signals linked to a card through card_signals; ordering comes from the pageable's sort. */
	@Query("""
		select s from RawSignal s
		where exists (select 1 from CardSignal cs where cs.signalId = s.id and cs.cardId = :cardId)
		""")
	Page<RawSignal> findByCardId(@Param("cardId") long cardId, Pageable pageable);
}
