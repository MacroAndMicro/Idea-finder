package com.idea_finder.repo.config;

import java.util.Map;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import com.idea_finder.repo.api.InvalidParameterException;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * IF-92: every query parameter of the card and ingestion-run endpoints is single-valued. Spring
 * would otherwise comma-join a repeated String param (misleading "must be one of" errors) or
 * silently keep the first value of a repeated number. A repeated parameter is rejected up front
 * with the standard 400 "Invalid request parameter" ProblemDetail naming it.
 */
@Configuration
public class SingleValueParamsConfig implements WebMvcConfigurer {

	static final String[] PATHS = { "/api/cards", "/api/cards/**", "/api/ingestion-runs", "/api/ingestion-runs/**" };

	@Override
	public void addInterceptors(InterceptorRegistry registry) {
		registry.addInterceptor(new SingleValueParamsInterceptor()).addPathPatterns(PATHS);
	}

	static final class SingleValueParamsInterceptor implements HandlerInterceptor {

		@Override
		public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
			for (Map.Entry<String, String[]> param : request.getParameterMap().entrySet()) {
				if (param.getValue() != null && param.getValue().length > 1) {
					throw new InvalidParameterException(param.getKey(),
						param.getKey() + " must be given at most once");
				}
			}
			return true;
		}
	}
}
