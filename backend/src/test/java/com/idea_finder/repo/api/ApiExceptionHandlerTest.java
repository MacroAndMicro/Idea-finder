package com.idea_finder.repo.api;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.math.BigDecimal;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.idea_finder.repo.config.RequestIdFilter;

/** Pure MVC slice (no DB): the error contract of {@link ApiExceptionHandler}. */
class ApiExceptionHandlerTest {

	static final String LEAK = "ERROR: relation \"opportunity_cards\" does not exist; password=hunter2";

	@RestController
	static class ThrowingController {

		@GetMapping("/boom")
		String boom() {
			throw new IllegalStateException(LEAK);
		}

		@GetMapping("/bad")
		String bad() {
			throw new InvalidParameterException("sort", "Unsupported sort 'x'");
		}

		@GetMapping("/typed/{id}")
		String typed(@PathVariable long id, @RequestParam(required = false) BigDecimal minConfidence,
				@RequestParam(required = false) Integer size) {
			return "ok";
		}

		@GetMapping("/missing")
		String missing() {
			throw new CardNotFoundException(42);
		}
	}

	MockMvc mvc;

	@BeforeEach
	void setUp() {
		mvc = MockMvcBuilders.standaloneSetup(new ThrowingController())
			.setControllerAdvice(new ApiExceptionHandler())
			.addFilters(new RequestIdFilter())
			.build();
	}

	@Test
	void unexpectedErrorIsGenericProblemDetailWithoutLeaks() throws Exception {
		mvc.perform(get("/boom"))
			.andExpect(status().isInternalServerError())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(500))
			.andExpect(jsonPath("$.title").value("Internal Server Error"))
			.andExpect(jsonPath("$.detail").value("Unexpected server error"))
			.andExpect(content().string(not(containsString("hunter2"))))
			.andExpect(content().string(not(containsString("opportunity_cards"))))
			.andExpect(content().string(not(containsString("IllegalStateException"))))
			.andExpect(content().string(not(containsString("at com."))))
			.andExpect(jsonPath("$.stackTrace").doesNotExist())
			.andExpect(jsonPath("$.requestId").isNotEmpty());
	}

	/** IF-54: the 500 body echoes the request's id. */
	@Test
	void unexpectedErrorCarriesRequestId() throws Exception {
		mvc.perform(get("/boom").header(RequestIdFilter.HEADER, "req-7"))
			.andExpect(status().isInternalServerError())
			.andExpect(jsonPath("$.requestId").value("req-7"));
	}

	@Test
	void invalidParameterIs400() throws Exception {
		mvc.perform(get("/bad"))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(400))
			.andExpect(jsonPath("$.title").value("Invalid request parameter"))
			.andExpect(jsonPath("$.detail").value("Unsupported sort 'x'"))
			.andExpect(jsonPath("$.parameter").value("sort"));
	}

	@Test
	void cardNotFoundIs404() throws Exception {
		mvc.perform(get("/missing"))
			.andExpect(status().isNotFound())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(404))
			.andExpect(jsonPath("$.title").value("Card not found"))
			.andExpect(jsonPath("$.detail").value("Card 42 not found"));
	}

	/** IF-95: conversion failures use the same shape as other parameter errors, without echoing input. */
	@Test
	void typeMismatchOnPathVariableNamesParameter() throws Exception {
		mvc.perform(get("/typed/<script>"))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.status").value(400))
			.andExpect(jsonPath("$.title").value("Invalid request parameter"))
			.andExpect(jsonPath("$.parameter").value("id"))
			.andExpect(jsonPath("$.detail").value("id must be a positive integer"))
			.andExpect(jsonPath("$.detail", not(containsString("script"))));
	}

	@Test
	void typeMismatchOnNanMinConfidence() throws Exception {
		mvc.perform(get("/typed/1").param("minConfidence", "NaN"))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.title").value("Invalid request parameter"))
			.andExpect(jsonPath("$.parameter").value("minConfidence"))
			.andExpect(jsonPath("$.detail").value("minConfidence must be a number between 0 and 100"))
			.andExpect(jsonPath("$.detail", not(containsString("NaN"))));
	}

	@Test
	void typeMismatchOnIntegerParamNamesType() throws Exception {
		mvc.perform(get("/typed/1").param("size", "1.5"))
			.andExpect(status().isBadRequest())
			.andExpect(jsonPath("$.parameter").value("size"))
			.andExpect(jsonPath("$.detail").value("size must be an integer"));
	}

	@Test
	void typedEndpointStillWorksWithValidValues() throws Exception {
		mvc.perform(get("/typed/7").param("minConfidence", "50").param("size", "3"))
			.andExpect(status().isOk());
	}
}
