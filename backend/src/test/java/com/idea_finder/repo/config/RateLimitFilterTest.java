package com.idea_finder.repo.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import com.idea_finder.repo.TestDb;

/** IF-67: per-IP rate limit on /api/**. Each test uses its own client IP so buckets don't interact. */
class RateLimitFilterTest {

	static RequestPostProcessor from(String ip) {
		return request -> {
			request.setRemoteAddr(ip);
			return request;
		};
	}

	@Nested
	@SpringBootTest(properties = {"app.rate-limit.per-minute=3", TestDb.ISOLATED_SCHEMA})
	@AutoConfigureMockMvc
	@DirtiesContext
	class DefaultSettings {

		@Autowired
		MockMvc mvc;

		@Test
		void underLimitPassesOverLimitIs429() throws Exception {
			for (int i = 0; i < 3; i++) {
				mvc.perform(get("/api/stats").with(from("10.0.0.1"))).andExpect(status().isOk());
			}
			mvc.perform(get("/api/stats").with(from("10.0.0.1")).header(RequestIdFilter.HEADER, "rl-test-1"))
				.andExpect(status().isTooManyRequests())
				.andExpect(header().string("Retry-After", "20"))
				.andExpect(header().string(RequestIdFilter.HEADER, "rl-test-1"))
				.andExpect(header().string("Cache-Control", "no-store"))
				.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
				.andExpect(jsonPath("$.status").value(429))
				.andExpect(jsonPath("$.title").value("Too Many Requests"))
				.andExpect(jsonPath("$.requestId").value("rl-test-1"))
				.andExpect(content().string(not(containsString("10.0.0.1"))));
			// another IP is unaffected
			mvc.perform(get("/api/no-such-endpoint").with(from("10.0.0.2"))).andExpect(status().isForbidden());
		}

		@Test
		void healthIsExempt() throws Exception {
			for (int i = 0; i < 10; i++) {
				mvc.perform(get("/api/health").with(from("10.0.1.1"))).andExpect(status().isOk());
			}
		}

		@Test
		void nonApiPathsAreNotCounted() throws Exception {
			for (int i = 0; i < 5; i++) {
				mvc.perform(get("/login").with(from("10.0.2.1"))).andExpect(status().isForbidden());
			}
			mvc.perform(get("/api/no-such-endpoint").with(from("10.0.2.1"))).andExpect(status().isForbidden());
		}

		@Test
		void forwardedHeaderIgnoredByDefault() throws Exception {
			for (int i = 0; i < 3; i++) {
				mvc.perform(get("/api/no-such-endpoint").with(from("10.0.3.1")).header("X-Forwarded-For", "1.1.1." + i))
					.andExpect(status().isForbidden());
			}
			// rotating X-Forwarded-For does not grant a fresh bucket
			mvc.perform(get("/api/no-such-endpoint").with(from("10.0.3.1")).header("X-Forwarded-For", "9.9.9.9"))
				.andExpect(status().isTooManyRequests());
		}
	}

	@Nested
	@SpringBootTest(properties = {"app.rate-limit.per-minute=2", "app.rate-limit.trust-forwarded-for=true"})
	@AutoConfigureMockMvc
	@DirtiesContext
	class BehindTrustedProxy {

		@Autowired
		MockMvc mvc;

		@Autowired
		RateLimitFilter filter;

		@Test
		void usesRightMostForwardedHop() throws Exception {
			for (int i = 0; i < 2; i++) {
				mvc.perform(get("/api/no-such-endpoint").with(from("10.9.9.9"))
						.header("X-Forwarded-For", "spoofed-" + i + ", 203.0.113.7"))
					.andExpect(status().isForbidden());
			}
			mvc.perform(get("/api/no-such-endpoint").with(from("10.9.9.9"))
					.header("X-Forwarded-For", "spoofed-x, 203.0.113.7"))
				.andExpect(status().isTooManyRequests());
			// a different real client behind the same proxy has its own bucket
			mvc.perform(get("/api/no-such-endpoint").with(from("10.9.9.9")).header("X-Forwarded-For", "203.0.113.8"))
				.andExpect(status().isForbidden());
		}

		@Test
		void fallsBackToRemoteAddrWithoutHeader() {
			MockHttpServletRequest request = new MockHttpServletRequest();
			request.setRemoteAddr("192.0.2.1");
			assertThat(filter.clientIp(request)).isEqualTo("192.0.2.1");
			request.addHeader("X-Forwarded-For", " , ");
			assertThat(filter.clientIp(request)).isEqualTo("192.0.2.1");
		}
	}
}
