package com.idea_finder.repo.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import com.idea_finder.repo.TestDb;

/** IF-36: GET /api/ingestion-runs on an empty if_test schema. */
@SpringBootTest(properties = TestDb.ISOLATED_SCHEMA)
@AutoConfigureMockMvc
@Transactional
@Sql(scripts = TestDb.SCHEMA, config = @SqlConfig(separator = TestDb.WHOLE_FILE))
class IngestionRunEmptyTest {

	@Autowired
	MockMvc mvc;

	@Test
	void emptyTableIsEmptyPage() throws Exception {
		mvc.perform(get("/api/ingestion-runs"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.items").isEmpty())
			.andExpect(jsonPath("$.total_elements").value(0))
			.andExpect(jsonPath("$.total_pages").value(0));
	}
}
