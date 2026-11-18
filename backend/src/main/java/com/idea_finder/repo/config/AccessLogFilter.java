package com.idea_finder.repo.config;

import java.io.IOException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * IF-78: one access-log line per {@code /api/**} request, written after the response is complete:
 * <pre>access method=GET path=/api/cards status=200 duration_ms=12 request_id=… client_ip=…</pre>
 * Only the method, the path (never the query string), the status, the duration, the request id
 * and the client IP are logged; headers, bodies and query values never are. {@code client_ip} is
 * present only when {@link RateLimitFilter} already resolved it (it honours
 * {@code API_TRUST_FORWARDED_FOR}); this filter never reads forwarding headers itself.
 * {@code /api/health} is logged at DEBUG so uptime probes don't flood the log; everything else at INFO.
 * <p>
 * Runs right after {@link RequestIdFilter} and before {@link RateLimitFilter}, so 429s are logged too.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 5)
public class AccessLogFilter extends OncePerRequestFilter {

	private static final Logger log = LoggerFactory.getLogger(AccessLogFilter.class);

	static final int MAX_PATH = 200;

	@Override
	protected boolean shouldNotFilter(HttpServletRequest request) {
		String path = path(request);
		return !(path.equals("/api") || path.startsWith("/api/"));
	}

	@Override
	protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
			throws ServletException, IOException {
		long start = System.nanoTime();
		boolean failed = true;
		try {
			chain.doFilter(request, response);
			failed = false;
		}
		finally {
			boolean health = path(request).equals("/api/health");
			if (health ? log.isDebugEnabled() : log.isInfoEnabled()) {
				// An exception escaping the chain means the container answers 500, whatever was set so far.
				String line = line(request.getMethod(), path(request), failed ? 500 : response.getStatus(),
					(System.nanoTime() - start) / 1_000_000, RequestIdFilter.current(request),
					request.getAttribute(RateLimitFilter.CLIENT_IP_ATTRIBUTE) instanceof String ip ? ip : null);
				if (health) {
					log.debug(line);
				}
				else {
					log.info(line);
				}
			}
		}
	}

	static String line(String method, String path, int status, long durationMs, String requestId, String clientIp) {
		StringBuilder sb = new StringBuilder(160)
			.append("access method=").append(safe(method, 16))
			.append(" path=").append(safe(path, MAX_PATH))
			.append(" status=").append(status)
			.append(" duration_ms=").append(durationMs)
			.append(" request_id=").append(requestId == null ? "-" : safe(requestId, 64));
		if (clientIp != null) {
			sb.append(" client_ip=").append(safe(clientIp, 64));
		}
		return sb.toString();
	}

	/** The request path without context path and without the query string. */
	private static String path(HttpServletRequest request) {
		return request.getRequestURI().substring(request.getContextPath().length());
	}

	/** Bounded, single-line, space-free value (no log injection through the path or method). */
	static String safe(String value, int max) {
		if (value == null || value.isEmpty()) {
			return "-";
		}
		StringBuilder sb = new StringBuilder(Math.min(value.length(), max));
		for (int i = 0; i < value.length() && sb.length() < max; i++) {
			char c = value.charAt(i);
			sb.append(c <= 0x20 || c == 0x7f ? '_' : c);
		}
		if (value.length() > max) {
			sb.append("...");
		}
		return sb.toString();
	}
}
