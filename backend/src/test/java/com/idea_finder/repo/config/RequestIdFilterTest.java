package com.idea_finder.repo.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.matchesPattern;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.idea_finder.repo.api.CardQueryService;

/** IF-54: X-Request-Id on every response, in the MDC, in 500 bodies and in the error log line. */
@SpringBootTest(properties = "FRONTEND_ORIGIN=https://app.example.com")
@AutoConfigureMockMvc
@ExtendWith(OutputCaptureExtension.class)
class RequestIdFilterTest {

	static final String UUID_PATTERN = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

	@Autowired
	MockMvc mvc;

	@MockitoBean
	CardQueryService cards;

	@Test
	void generatesIdWhenAbsent() throws Exception {
		mvc.perform(get("/api/health"))
			.andExpect(header().string(RequestIdFilter.HEADER, matchesPattern(UUID_PATTERN)));
	}

	@Test
	void propagatesValidIncomingId() throws Exception {
		mvc.perform(get("/api/health").header(RequestIdFilter.HEADER, "abc-123-XYZ"))
			.andExpect(header().string(RequestIdFilter.HEADER, "abc-123-XYZ"));
		String max = "a".repeat(64);
		mvc.perform(get("/api/health").header(RequestIdFilter.HEADER, max))
			.andExpect(header().string(RequestIdFilter.HEADER, max));
	}

	@ParameterizedTest
	@ValueSource(strings = {"", " ", "has space", "semi;colon", "new\nline", "under_score", "ünïcode",
		"<script>", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"})
	void invalidIncomingIdIsReplaced(String bad) throws Exception {
		mvc.perform(get("/api/health").header(RequestIdFilter.HEADER, bad))
			.andExpect(header().string(RequestIdFilter.HEADER, matchesPattern(UUID_PATTERN)));
	}

	@Test
	void deniedRequestsGetAnIdToo() throws Exception {
		mvc.perform(post("/api/cards"))
			.andExpect(status().isForbidden())
			.andExpect(header().string(RequestIdFilter.HEADER, matchesPattern(UUID_PATTERN)));
	}

	@Test
	void corsExposesTheHeader() throws Exception {
		mvc.perform(get("/api/health").header(HttpHeaders.ORIGIN, "https://app.example.com"))
			.andExpect(header().string(HttpHeaders.ACCESS_CONTROL_EXPOSE_HEADERS, RequestIdFilter.HEADER));
		mvc.perform(options("/api/cards")
				.header(HttpHeaders.ORIGIN, "https://app.example.com")
				.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
				.header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, RequestIdFilter.HEADER))
			.andExpect(status().isOk());
	}

	@Test
	void unhandledErrorBodyAndLogLineCarryTheId(CapturedOutput output) throws Exception {
		given(cards.get(anyLong())).willThrow(new IllegalStateException("db password=hunter2"));
		MvcResult result = mvc.perform(get("/api/cards/7").header(RequestIdFilter.HEADER, "qa-run-42"))
			.andExpect(status().isInternalServerError())
			.andExpect(header().string(RequestIdFilter.HEADER, "qa-run-42"))
			.andExpect(jsonPath("$.requestId").value("qa-run-42"))
			.andExpect(jsonPath("$.detail").value("Unexpected server error"))
			.andReturn();
		assertThat(result.getResponse().getContentAsString()).doesNotContain("hunter2", "IllegalStateException");
		assertThat(output).contains("Unhandled API error [requestId=qa-run-42]");
	}

	@Test
	void mdcIsClearedAfterTheRequest() throws Exception {
		mvc.perform(get("/api/health").header(RequestIdFilter.HEADER, "leak-check"));
		assertThat(MDC.get(RequestIdFilter.MDC_KEY)).isNull();
	}

	@Test
	void resolveRules() {
		assertThat(RequestIdFilter.resolve("ok-1")).isEqualTo("ok-1");
		assertThat(RequestIdFilter.resolve(null)).matches(UUID_PATTERN);
		assertThat(RequestIdFilter.resolve("a".repeat(65))).matches(UUID_PATTERN);
	}
}
