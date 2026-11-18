package com.idea_finder.repo.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.sql.SQLException;

import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import com.idea_finder.repo.config.RequestIdFilter;

/** IF-66: /api/health reports database reachability. */
class HealthDatabaseTest {

	/** Up path against the real test database. */
	@SpringBootTest
	@AutoConfigureMockMvc
	@org.junit.jupiter.api.Nested
	class DatabaseUp {

		@Autowired
		MockMvc mvc;

		@Autowired
		DatabaseHealthProbe probe;

		@Test
		void okWhenDatabaseAnswers() throws Exception {
			assertThat(probe.isUp()).isTrue();
			mvc.perform(get("/api/health"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.status").value("ok"))
				.andExpect(jsonPath("$.db").value("up"))
				.andExpect(jsonPath("$.keys()").value(org.hamcrest.Matchers.contains("status", "db")));
		}

		@Test
		void stillGetOnly() throws Exception {
			mvc.perform(post("/api/health")).andExpect(status().isForbidden());
		}
	}

	/** Down path: the probe reports failure, the endpoint answers 503 without internals. */
	@SpringBootTest
	@AutoConfigureMockMvc
	@org.junit.jupiter.api.Nested
	class DatabaseDown {

		@Autowired
		MockMvc mvc;

		@MockitoBean
		DatabaseHealthProbe probe;

		@Test
		void degradedWhenDatabaseDown() throws Exception {
			given(probe.isUp()).willReturn(false);
			mvc.perform(get("/api/health"))
				.andExpect(status().isServiceUnavailable())
				.andExpect(jsonPath("$.status").value("degraded"))
				.andExpect(jsonPath("$.db").value("down"))
				.andExpect(header().exists(RequestIdFilter.HEADER))
				.andExpect(header().string("Cache-Control", containsString("no-store")))
				.andExpect(content().string(not(containsString("Exception"))));
		}
	}

	/** Probe unit tests with a DataSource that cannot connect. */
	@org.junit.jupiter.api.Nested
	@ExtendWith(OutputCaptureExtension.class)
	class Probe {

		@Test
		void downWhenConnectionFailsAndLogsWithoutDetails(CapturedOutput output) throws Exception {
			DataSource broken = mock(DataSource.class);
			given(broken.getConnection()).willThrow(new SQLException("connect to db.secret-host.internal failed"));
			DatabaseHealthProbe p = new DatabaseHealthProbe(broken, 2);
			assertThat(p.isUp()).isFalse();
			assertThat(output.getOut()).contains("Health check: database unreachable");
			assertThat(output.getOut()).doesNotContain("secret-host");
		}
	}
}
