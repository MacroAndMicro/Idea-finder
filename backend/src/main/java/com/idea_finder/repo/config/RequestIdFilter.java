package com.idea_finder.repo.config;

import java.io.IOException;
import java.util.UUID;
import java.util.regex.Pattern;

import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * IF-54: every request gets an id that links client-visible errors to server log lines. A valid
 * incoming {@value #HEADER} (≤ 64 chars of [A-Za-z0-9-]) is reused, anything else is replaced by a
 * random UUID. The id is put in the MDC (key {@value #MDC_KEY}), in a request attribute and in the
 * response header. Runs before Spring Security so denied requests get one too.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestIdFilter extends OncePerRequestFilter {

	public static final String HEADER = "X-Request-Id";
	public static final String MDC_KEY = "requestId";
	public static final String ATTRIBUTE = RequestIdFilter.class.getName() + ".requestId";

	private static final Pattern VALID = Pattern.compile("[A-Za-z0-9-]{1,64}");

	@Override
	protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
			throws ServletException, IOException {
		String id = resolve(request.getHeader(HEADER));
		request.setAttribute(ATTRIBUTE, id);
		response.setHeader(HEADER, id);
		MDC.put(MDC_KEY, id);
		try {
			chain.doFilter(request, response);
		}
		finally {
			MDC.remove(MDC_KEY);
		}
	}

	/** The incoming id when valid, otherwise a new random one. */
	static String resolve(String incoming) {
		if (incoming != null && VALID.matcher(incoming).matches()) {
			return incoming;
		}
		return UUID.randomUUID().toString();
	}

	/** The current request's id: the request attribute, then the MDC; null outside a filtered request. */
	public static String current(HttpServletRequest request) {
		Object attribute = request == null ? null : request.getAttribute(ATTRIBUTE);
		return attribute instanceof String s ? s : MDC.get(MDC_KEY);
	}
}
