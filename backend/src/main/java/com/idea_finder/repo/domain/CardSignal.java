package com.idea_finder.repo.domain;

import java.io.Serializable;

import org.hibernate.annotations.Immutable;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/** Read-only view of the public.card_signals link table (card -> supporting raw signals). */
@Entity
@Immutable
@Table(name = "card_signals")
@IdClass(CardSignal.Key.class)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class CardSignal {

	@Id
	@Column(name = "card_id")
	private Long cardId;

	@Id
	@Column(name = "signal_id")
	private Long signalId;

	public record Key(Long cardId, Long signalId) implements Serializable {
	}
}
