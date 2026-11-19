package com.idea_finder.repo.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

@SpringBootTest(properties = "app.cors.allowed-origins=http://localhost:3000,https://app.example.test")
@AutoConfigureMockMvc
class HealthAndSecurityTest {

	@Autowired
	MockMvc mvc;

	@Test
	void healthIsPublic() throws Exception {
		mvc.perform(get("/api/health"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.status").value("ok"));
	}

	@Test
	void unknownEndpointIsDenied() throws Exception {
		mvc.perform(get("/api/admin")).andExpect(status().isForbidden());
		mvc.perform(get("/actuator/env")).andExpect(status().isForbidden());
	}

	@Test
	void writesAreDeniedEvenOnPublicPaths() throws Exception {
		mvc.perform(post("/api/cards").contentType("application/json").content("{}"))
			.andExpect(status().isForbidden());
		mvc.perform(post("/api/health")).andExpect(status().isForbidden());
	}

	/** IF-90: a 403 from Spring Security is an RFC 9457 ProblemDetail like every other API error. */
	@Test
	void deniedRequestsReturnProblemDetail() throws Exception {
		assertForbiddenProblem(mvc.perform(get("/api/nope")));
		assertForbiddenProblem(mvc.perform(post("/api/cards").contentType("application/json").content("{}")));
		assertForbiddenProblem(mvc.perform(delete("/api/cards")));
	}

	@Test
	void deniedProblemDetailEchoesValidRequestId() throws Exception {
		mvc.perform(get("/api/nope").header("X-Request-Id", "abc-123"))
			.andExpect(status().isForbidden())
			.andExpect(header().string("X-Request-Id", "abc-123"))
			.andExpect(jsonPath("$.requestId").value("abc-123"));
	}

	private static void assertForbiddenProblem(ResultActions result) throws Exception {
		result.andExpect(status().isForbidden())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(header().exists("X-Request-Id"))
			.andExpect(jsonPath("$.type").value("about:blank"))
			.andExpect(jsonPath("$.title").value("Forbidden"))
			.andExpect(jsonPath("$.status").value(403))
			.andExpect(jsonPath("$.detail").isString())
			.andExpect(jsonPath("$.requestId").isString())
			.andExpect(jsonPath("$.timestamp").doesNotExist());
	}

	@Test
	void noBasicAuthOrLoginPage() throws Exception {
		mvc.perform(get("/login")).andExpect(status().isForbidden());
		mvc.perform(get("/api/admin").header("Authorization", "Basic dXNlcjpwYXNz"))
			.andExpect(status().isForbidden());
	}

	@Test
	void corsPreflightFromAllowedOrigin() throws Exception {
		mvc.perform(options("/api/cards")
				.header("Origin", "https://app.example.test")
				.header("Access-Control-Request-Method", "GET"))
			.andExpect(status().isOk())
			.andExpect(header().string("Access-Control-Allow-Origin", "https://app.example.test"));
	}

	@Test
	void corsPreflightFromUnknownOriginIsRejected() throws Exception {
		mvc.perform(options("/api/cards")
				.header("Origin", "https://evil.example.test")
				.header("Access-Control-Request-Method", "GET"))
			.andExpect(status().isForbidden())
			.andExpect(header().doesNotExist("Access-Control-Allow-Origin"));
	}

	@Test
	void corsPreflightForDisallowedMethodIsRejected() throws Exception {
		mvc.perform(options("/api/cards")
				.header("Origin", "http://localhost:3000")
				.header("Access-Control-Request-Method", "DELETE"))
			.andExpect(status().isForbidden());
	}
}
