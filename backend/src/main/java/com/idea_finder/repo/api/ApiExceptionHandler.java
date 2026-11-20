package com.idea_finder.repo.api;

import java.math.BigDecimal;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.TypeMismatchException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
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

	/**
	 * IF-95: a query/path value that cannot be converted to the declared type (e.g. {@code id=abc},
	 * {@code minConfidence=NaN}) gets the same shape as {@link #invalidParameter}: title, a
	 * {@code parameter} field and a message naming the expected type. The rejected value is never
	 * echoed back (no reflection of arbitrary input).
	 */
	@Override
	protected ResponseEntity<Object> handleTypeMismatch(TypeMismatchException ex, HttpHeaders headers,
			HttpStatusCode status, WebRequest request) {
		String parameter = ex instanceof MethodArgumentTypeMismatchException mismatch
			? mismatch.getName()
			: ex.getPropertyName();
		ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST,
			typeMismatchMessage(parameter, ex.getRequiredType()));
		pd.setTitle("Invalid request parameter");
		pd.setProperty("parameter", parameter);
		return handleExceptionInternal(ex, pd, headers, HttpStatus.BAD_REQUEST, request);
	}

	static String typeMismatchMessage(String parameter, Class<?> requiredType) {
		String name = parameter == null ? "parameter" : parameter;
		if ("minConfidence".equals(name)) {
			return "minConfidence must be a number between 0 and 100";
		}
		if ("id".equals(name)) {
			return "id must be a positive integer";
		}
		if (requiredType == null) {
			return name + " has an invalid value";
		}
		if (requiredType == int.class || requiredType == Integer.class
				|| requiredType == long.class || requiredType == Long.class) {
			return name + " must be an integer";
		}
		if (requiredType == BigDecimal.class || requiredType == double.class || requiredType == Double.class) {
			return name + " must be a number";
		}
		if (requiredType == boolean.class || requiredType == Boolean.class) {
			return name + " must be true or false";
		}
		return name + " has an invalid value";
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
