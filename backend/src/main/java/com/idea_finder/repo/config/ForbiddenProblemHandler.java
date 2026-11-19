package com.idea_finder.repo.config;

import java.io.IOException;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * IF-90: requests that Spring Security denies (unknown paths, non-GET methods) are answered with
 * 403 and an RFC 9457 ProblemDetail body, like every other API error, instead of Spring's default
 * error JSON. There is no authentication yet, so an anonymous request reaches the entry point and an
 * authenticated one (none today) the access-denied handler; both get the same response.
 */
final class ForbiddenProblemHandler implements AuthenticationEntryPoint, AccessDeniedHandler {

	static final String DETAIL = "This endpoint or method is not available.";

	@Override
	public void commence(HttpServletRequest request, HttpServletResponse response,
			AuthenticationException authException) throws IOException {
		write(request, response);
	}

	@Override
	public void handle(HttpServletRequest request, HttpServletResponse response,
			AccessDeniedException accessDeniedException) throws IOException {
		write(request, response);
	}

	private static void write(HttpServletRequest request, HttpServletResponse response) throws IOException {
		if (response.isCommitted()) {
			return;
		}
		String requestId = RequestIdFilter.current(request);
		response.setStatus(HttpStatus.FORBIDDEN.value());
		response.setHeader(HttpHeaders.CACHE_CONTROL, "no-store");
		response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
		response.setCharacterEncoding("UTF-8");
		// The request id is restricted to [A-Za-z0-9-] by RequestIdFilter, so it is JSON-safe.
		String id = requestId == null ? "" : ",\"requestId\":\"" + requestId + "\"";
		response.getWriter().write("{\"type\":\"about:blank\",\"title\":\"Forbidden\",\"status\":403,"
			+ "\"detail\":\"" + DETAIL + "\"" + id + "}");
	}
}
