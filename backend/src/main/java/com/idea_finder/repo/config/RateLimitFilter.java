package com.idea_finder.repo.config;

import java.io.IOException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * IF-67: per-client-IP rate limit on {@code /api/**} ({@code /api/health} exempt). Over the limit the
 * request is answered with 429, a {@code Retry-After} header and an RFC 9457 ProblemDetail body that
 * carries only the request id. Runs right after {@link RequestIdFilter} and before Spring Security.
 * <p>
 * The client IP is the socket's remote address. {@code X-Forwarded-For} is read only when
 * {@code API_TRUST_FORWARDED_FOR=true} (the API sits behind a trusted reverse proxy); then the
 * right-most entry, the one appended by that proxy, is used, since earlier entries are client-controlled.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class RateLimitFilter extends OncePerRequestFilter {

	private static final Logger log = LoggerFactory.getLogger(RateLimitFilter.class);

	static final String FORWARDED_FOR = "X-Forwarded-For";

	private final RateLimiter limiter;
	private final boolean trustForwardedFor;

	public RateLimitFilter(@Value("${app.rate-limit.per-minute:120}") int perMinute,
			@Value("${app.rate-limit.max-clients:10000}") int maxClients,
			@Value("${app.rate-limit.trust-forwarded-for:false}") boolean trustForwardedFor) {
		this.limiter = new RateLimiter(perMinute, maxClients, System::nanoTime);
		this.trustForwardedFor = trustForwardedFor;
	}

	@Override
	protected boolean shouldNotFilter(HttpServletRequest request) {
		String path = request.getRequestURI().substring(request.getContextPath().length());
		return !(path.equals("/api") || path.startsWith("/api/")) || path.equals("/api/health");
	}

	@Override
	protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
			throws ServletException, IOException {
		RateLimiter.Decision decision = limiter.tryAcquire(clientIp(request));
		if (decision.allowed()) {
			chain.doFilter(request, response);
			return;
		}
		String requestId = RequestIdFilter.current(request);
		log.info("Rate limit exceeded [requestId={}]", requestId);
		response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
		response.setHeader(HttpHeaders.RETRY_AFTER, Long.toString(decision.retryAfterSeconds()));
		response.setHeader(HttpHeaders.CACHE_CONTROL, "no-store");
		response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
		response.setCharacterEncoding("UTF-8");
		// The request id is restricted to [A-Za-z0-9-] by RequestIdFilter, so it is JSON-safe.
		String id = requestId == null ? "" : ",\"requestId\":\"" + requestId + "\"";
		response.getWriter().write("{\"type\":\"about:blank\",\"title\":\"Too Many Requests\",\"status\":429,"
			+ "\"detail\":\"Rate limit exceeded; retry after the time given in Retry-After.\"" + id + "}");
	}

	String clientIp(HttpServletRequest request) {
		if (trustForwardedFor) {
			String header = request.getHeader(FORWARDED_FOR);
			if (header != null) {
				String[] hops = header.split(",");
				for (int i = hops.length - 1; i >= 0; i--) {
					String hop = hops[i].strip();
					if (!hop.isEmpty() && hop.length() <= 64) {
						return hop;
					}
				}
			}
		}
		return request.getRemoteAddr();
	}
}
