package com.idea_finder.repo.api;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

import com.idea_finder.repo.config.RequestIdFilter;

import jakarta.servlet.http.HttpServletRequest;

/**
 * Every API error is an RFC 9457 ProblemDetail (application/problem+json).
 * The base class covers framework errors (type mismatch, missing params, 405, ...).
 */
@RestControllerAdvice
public class ApiExceptionHandler extends ResponseEntityExceptionHandler {

	private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

	@ExceptionHandler(InvalidParameterException.class)
	ProblemDetail invalidParameter(InvalidParameterException ex) {
		ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, ex.getMessage());
		pd.setTitle("Invalid request parameter");
		pd.setProperty("parameter", ex.getParameter());
		return pd;
	}

	@ExceptionHandler(CardNotFoundException.class)
	ProblemDetail notFound(CardNotFoundException ex) {
		ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
		pd.setTitle("Card not found");
		return pd;
	}

	/**
	 * Never leak internals (SQL, stack traces) to clients. IF-54: the body carries the request id,
	 * which is also on the log line, so a client-side error can be matched to the server log.
	 */
	@ExceptionHandler(Exception.class)
	ProblemDetail unexpected(Exception ex, HttpServletRequest request) {
		String requestId = RequestIdFilter.current(request);
		log.error("Unhandled API error [requestId={}]", requestId, ex);
		ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR,
			"Unexpected server error");
		pd.setTitle("Internal Server Error");
		if (requestId != null) {
			pd.setProperty("requestId", requestId);
		}
		return pd;
	}
}
