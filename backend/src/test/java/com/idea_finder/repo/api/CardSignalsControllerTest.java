package com.idea_finder.repo.api;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasKey;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.TestDb;

/** IF-16: GET /api/cards/{id}/signals, full stack against the if_test schema. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = {TestDb.SCHEMA, TestDb.DATA}, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class CardSignalsControllerTest {

	@Autowired
	MockMvc mvc;

	@Test
	void listsLinkedSignalsNewestFirst() throws Exception {
		mvc.perform(get("/api/cards/1/signals"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(2, 1)))
			.andExpect(jsonPath("$.page").value(0))
			.andExpect(jsonPath("$.size").value(20))
			.andExpect(jsonPath("$.total_elements").value(2))
			.andExpect(jsonPath("$.total_pages").value(1));
	}

	@Test
	void responseShapeHasNoHashes() throws Exception {
		mvc.perform(get("/api/cards/1/signals"))
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
			.andExpect(jsonPath("$.items[0].id").value(2))
			.andExpect(jsonPath("$.items[0].source_platform").value("hackernews"))
			.andExpect(jsonPath("$.items[0].url").value("https://news.ycombinator.com/item?id=42"))
			.andExpect(jsonPath("$.items[0].title").value("Ask HN: flaky tests"))
			.andExpect(jsonPath("$.items[0].body_snippet").value("short body"))
			.andExpect(jsonPath("$.items[0].score").value(55))
			.andExpect(jsonPath("$.items[0].comment_count").value(20))
			.andExpect(jsonPath("$.items[0].source_created_at").exists())
			.andExpect(jsonPath("$.items[0]", not(hasKey("author_handle_hash"))))
			.andExpect(jsonPath("$.items[0]", not(hasKey("authorHandleHash"))))
			.andExpect(jsonPath("$.items[0]", not(hasKey("content_hash"))))
			.andExpect(jsonPath("$.items[0]", not(hasKey("contentHash"))))
			.andExpect(content().string(not(org.hamcrest.Matchers.containsString("authhash"))))
			.andExpect(content().string(not(org.hamcrest.Matchers.containsString("contenthash"))));
	}

	@Test
	void longBodyIsTruncatedTo500Chars() throws Exception {
		mvc.perform(get("/api/cards/1/signals"))
			.andExpect(jsonPath("$.items[1].id").value(1))
			.andExpect(jsonPath("$.items[1].body_snippet").value("x".repeat(500)));
	}

	@Test
	void nullFieldsStayNull() throws Exception {
		mvc.perform(get("/api/cards/2/signals"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(3)))
			.andExpect(jsonPath("$.items[0].body_snippet").doesNotExist())
			.andExpect(jsonPath("$.items[0].source_created_at").doesNotExist());
	}

	@Test
	void cardWithZeroSignalsReturnsEmptyPage() throws Exception {
		mvc.perform(get("/api/cards/3/signals"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items").isEmpty())
			.andExpect(jsonPath("$.total_elements").value(0))
			.andExpect(jsonPath("$.total_pages").value(0));
	}

	@Test
	void paging() throws Exception {
		mvc.perform(get("/api/cards/1/signals").param("page", "1").param("size", "1"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items[*].id").value(contains(1)))
			.andExpect(jsonPath("$.total_pages").value(2));
	}

	@Test
	void unknownCardReturns404ProblemDetail() throws Exception {
		mvc.perform(get("/api/cards/999/signals"))
			.andExpect(status().isNotFound())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.detail").value("Card 999 not found"));
	}

	@ParameterizedTest
	@CsvSource({"size, 51", "size, 0", "page, -1", "page, 10001"})
	void invalidPagingReturns400ProblemDetail(String name, String value) throws Exception {
		mvc.perform(get("/api/cards/1/signals").param(name, value))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
			.andExpect(jsonPath("$.parameter").value(name));
	}

	@Test
	void malformedIdReturns400() throws Exception {
		mvc.perform(get("/api/cards/abc/signals"))
			.andExpect(status().isBadRequest())
			.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON));
	}
}
