package com.idea_finder.repo.api;

public class CardNotFoundException extends RuntimeException {

	public CardNotFoundException(long id) {
		super("Card " + id + " not found");
	}
}
