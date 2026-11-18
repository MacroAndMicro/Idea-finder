package com.idea_finder.repo.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;

class CorsConfigTest {

	private CorsConfiguration configFor(String allowedOrigins) {
		CorsConfigurationSource source = new CorsConfig().corsConfigurationSource(allowedOrigins);
		MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/cards");
		request.setServletPath("/api/cards");
		return source.getCorsConfiguration(request);
	}

	@Test
	void defaultLocalhostOriginIsAllowed() {
		CorsConfiguration config = configFor("http://localhost:3000");
		assertThat(config.checkOrigin("http://localhost:3000")).isEqualTo("http://localhost:3000");
	}

	@Test
	void commaSeparatedOriginsAreTrimmed() {
		CorsConfiguration config = configFor(" https://a.example.com ,  https://b.example.com,, ");
		assertThat(config.getAllowedOrigins()).containsExactly("https://a.example.com", "https://b.example.com");
		assertThat(config.checkOrigin("https://b.example.com")).isEqualTo("https://b.example.com");
	}

	@Test
	void disallowedOriginIsRejected() {
		CorsConfiguration config = configFor("https://a.example.com");
		assertThat(config.checkOrigin("https://evil.example.com")).isNull();
	}

	@Test
	void methodsAreReadOnlyAndCredentialsOff() {
		CorsConfiguration config = configFor("https://a.example.com");
		assertThat(config.getAllowedMethods()).containsExactly("GET", "HEAD", "OPTIONS");
		assertThat(config.getAllowCredentials()).isFalse();
	}
}
