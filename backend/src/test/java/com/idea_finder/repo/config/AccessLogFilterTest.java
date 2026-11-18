package com.idea_finder.repo.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import java.util.regex.Pattern;

import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.logging.LogLevel;
import org.springframework.boot.logging.LoggingSystem;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import com.idea_finder.repo.api.CardQueryService;

/** IF-78: one access-log line per /api/** request; never headers, bodies or query values. */
class AccessLogFilterTest {

	static final Pattern LINE = Pattern.compile(
		"INFO \\[[^\\]]*\\] .* access method=GET path=/api/cards status=200 duration_ms=\\d+ request_id=log-test-1"
			+ " client_ip=127\\.0\\.0\\.1$", Pattern.MULTILINE);

	static List<String> accessLines(CapturedOutput output) {
		return output.getOut().lines().filter(l -> l.contains(" access method=")).toList();
	}

	static List<String> infoAccessLines(CapturedOutput output) {
		return accessLines(output).stream().filter(l -> l.contains(" INFO [")).toList();
	}

	@Nested
	@SpringBootTest(properties = "app.rate-limit.per-minute=1000")
	@AutoConfigureMockMvc
	@ExtendWith(OutputCaptureExtension.class)
	class Defaults {

		@Autowired
		MockMvc mvc;

		@MockitoBean
		CardQueryService cards;

		@Test
		void logsOneInfoLineWithoutQueryValuesOrHeaders(CapturedOutput output) throws Exception {
			mvc.perform(get("/api/cards").param("q", "secret-query-value").param("source", "github")
					.header(HttpHeaders.AUTHORIZATION, "Bearer top-secret-token")
					.header(HttpHeaders.COOKIE, "session=cookie-secret")
					.header(RequestIdFilter.HEADER, "log-test-1"))
				.andExpect(status().isOk());
			assertThat(infoAccessLines(output)).hasSize(1);
			assertThat(output.getOut()).containsPattern(LINE);
			assertThat(output.getAll()).doesNotContain("secret-query-value", "top-secret-token", "Bearer",
				"cookie-secret", "source=github", "q=");
		}

		@Test
		void logsErrorStatuses(CapturedOutput output) throws Exception {
			mvc.perform(post("/api/cards").header(RequestIdFilter.HEADER, "log-403")).andExpect(status().isForbidden());
			mvc.perform(get("/api/cards/not-a-number").header(RequestIdFilter.HEADER, "log-400"))
				.andExpect(status().isBadRequest());
			assertThat(output.getOut())
				.containsPattern("access method=POST path=/api/cards status=403 duration_ms=\\d+ request_id=log-403")
				.containsPattern("access method=GET path=/api/cards/not-a-number status=400 duration_ms=\\d+ request_id=log-400");
			assertThat(infoAccessLines(output)).hasSize(2);
		}

		@Test
		void healthIsNotLoggedAtInfo(CapturedOutput output) throws Exception {
			mvc.perform(get("/api/health"));
			assertThat(infoAccessLines(output)).isEmpty();
		}

		@Test
		void nonApiPathsAreNotLogged(CapturedOutput output) throws Exception {
			mvc.perform(get("/not-api"));
			assertThat(accessLines(output)).isEmpty();
		}
	}

	@Nested
	@SpringBootTest(properties = {"app.rate-limit.per-minute=2", "app.rate-limit.trust-forwarded-for=true"})
	@AutoConfigureMockMvc
	@ExtendWith(OutputCaptureExtension.class)
	class DebugAndTrustedProxy {

		@Autowired
		MockMvc mvc;

		@MockitoBean
		CardQueryService cards;

		@Test
		void healthIsLoggedAtDebugWithoutClientIp(CapturedOutput output) throws Exception {
			LoggingSystem logging = LoggingSystem.get(getClass().getClassLoader());
			logging.setLogLevel(AccessLogFilter.class.getName(), LogLevel.DEBUG);
			try {
				mvc.perform(get("/api/health").header(RequestIdFilter.HEADER, "probe-1"));
			}
			finally {
				logging.setLogLevel(AccessLogFilter.class.getName(), null);
			}
			assertThat(accessLines(output)).singleElement().asString()
				.containsPattern("DEBUG \\[probe-1\\] .* access method=GET path=/api/health status=\\d{3} "
					+ "duration_ms=\\d+ request_id=probe-1$")
				.doesNotContain("client_ip=");
		}

		@Test
		void clientIpIsTheOneTheRateLimiterResolvedAnd429IsLogged(CapturedOutput output) throws Exception {
			for (int i = 0; i < 3; i++) {
				mvc.perform(get("/api/cards").header(RateLimitFilter.FORWARDED_FOR, "198.51.100.7, 203.0.113.9"));
			}
			List<String> lines = infoAccessLines(output);
			assertThat(lines).hasSize(3).allSatisfy(l -> assertThat(l).endsWith(" client_ip=203.0.113.9"));
			assertThat(lines.get(2)).contains(" status=429 ");
			assertThat(output.getAll()).doesNotContain("198.51.100.7");
		}
	}

	@Test
	void lineIsSingleLineAndBounded() {
		String line = AccessLogFilter.line("GET", "/api/cards/a b\r\nINFO forged", 404, 3, null, null);
		assertThat(line).isEqualTo("access method=GET path=/api/cards/a_b__INFO_forged status=404 duration_ms=3 request_id=-");
		assertThat(AccessLogFilter.line("GET", "/api/" + "x".repeat(500), 404, 1, "r", "1.2.3.4"))
			.contains("x".repeat(AccessLogFilter.MAX_PATH - 5) + "... status=404")
			.endsWith(" client_ip=1.2.3.4");
	}
}
