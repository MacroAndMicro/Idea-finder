package com.idea_finder.repo.api;

/** A query parameter failed validation; rendered as a 400 ProblemDetail. */
public class InvalidParameterException extends RuntimeException {

	private final String parameter;

	public InvalidParameterException(String parameter, String message) {
		super(message);
		this.parameter = parameter;
	}

	public String getParameter() {
		return parameter;
	}
}
