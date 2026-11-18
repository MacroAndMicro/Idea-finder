# syntax=docker/dockerfile:1
# IF-76: production image of the Spring Boot API (host-neutral; see README "Docker").
# Build from backend/:  docker build -t idea-finder-api .
# All configuration comes from environment variables at run time; nothing secret is baked in.

# ---- build: JDK 21 + Maven wrapper -------------------------------------------------------------
FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
# Dependencies first so they are cached until pom.xml changes.
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
RUN --mount=type=cache,target=/root/.m2 chmod +x mvnw && ./mvnw -B -q dependency:go-offline
COPY src/ src/
RUN --mount=type=cache,target=/root/.m2 ./mvnw -B -q -DskipTests package \
	&& cp target/repo-*.jar /src/app.jar \
	&& mkdir /src/layers && cd /src/layers && java -Djarmode=tools -jar /src/app.jar extract --layers --launcher --destination .

# ---- runtime: JRE 21, non-root -----------------------------------------------------------------
FROM eclipse-temurin:21-jre
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
# Spring Boot layers, least to most frequently changing.
COPY --from=build /src/layers/dependencies/ ./
COPY --from=build /src/layers/spring-boot-loader/ ./
COPY --from=build /src/layers/snapshot-dependencies/ ./
COPY --from=build /src/layers/application/ ./
USER app:app
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75 -XX:+ExitOnOutOfMemoryError" \
	SERVER_PORT=8080
EXPOSE 8080
# /api/health answers 200 when the API and its database are up, 503 otherwise.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
	CMD curl -fsS -o /dev/null "http://127.0.0.1:${SERVER_PORT}/api/health" || exit 1
ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
