# Idea Finder

Automated market-intelligence platform. It ingests unstructured user feedback and technical
discussions (Reddit, GitHub Issues, Hacker News, Stack Exchange) and turns them into
evidence-backed software opportunities ("Opportunity Cards") with a B2B / developer focus.

Work is done by a team of AI agents that take tickets from a Supabase-backed board and ship
changes as GitLab merge requests (MRs). GitLab is the source of truth; the GitHub copy is a
read-only mirror that runs CI.

## Repository layout

| Path | What | Stack |
|---|---|---|
| `backend/` | REST API over the opportunity-card data | Java 21, Spring Boot 4.1, Maven, Spring Data JPA, Spring Security, PostgreSQL |
| `frontend/` | Web UI (talks to the backend API only) | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4 |
| `scrapers/` | Ingestion adapters and LLM pipeline (in progress) | Python 3.12, pytest, ruff |
| `supabase/migrations/` | The only place schema changes live | SQL, `YYYYMMDDHHMMSS_name.sql` |
| `prompts/` | Agent prompts and the operating manual | Markdown |

## Local development

```bash
# backend
cd backend && ./mvnw verify

# frontend
cd frontend && npm ci && npm run lint && npm run build

# scrapers
pip install -r scrapers/requirements.txt && ruff check scrapers && pytest scrapers
```

## API

The backend's endpoints, parameters, errors and example responses are documented in
[`docs/api.md`](docs/api.md).

## Configuration

Secrets and settings come only from environment variables. Copy `.env.example` to `.env`
and fill it in; the file lists every variable by name. Never commit `.env` or any value.

The backend's `DATABASE_URL` points at the Supabase **transaction pooler** (port 6543). The
defaults in `backend/src/main/resources/application.yaml` are tuned for it and can be
overridden with environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `DB_PREPARE_THRESHOLD` | `0` | JDBC `prepareThreshold`; keep `0` behind the pooler (server-side prepared statements break) |
| `DB_POOL_MAX_SIZE` | `5` | Hikari maximum pool size |
| `DB_POOL_MIN_IDLE` | `1` | Hikari minimum idle connections |
| `DB_CONNECTION_TIMEOUT_MS` | `10000` | Max wait for a pooled connection |
| `DB_IDLE_TIMEOUT_MS` | `300000` | Idle connection retirement |
| `DB_MAX_LIFETIME_MS` | `900000` | Max connection lifetime |
| `SHUTDOWN_TIMEOUT` | `20s` | Graceful-shutdown grace period |
| `API_RATE_LIMIT_PER_MINUTE` | `120` | Requests per minute per client IP on `/api/**` (`/api/health` exempt); over it: 429 + `Retry-After` |
| `API_RATE_LIMIT_MAX_CLIENTS` | `10000` | Max client IPs tracked in memory (idle ones evicted first) |
| `API_TRUST_FORWARDED_FOR` | `false` | Set `true` only behind a trusted reverse proxy: the client IP is then the right-most `X-Forwarded-For` entry |
| `API_AGGREGATE_CACHE_MAX_AGE` | `60s` | `Cache-Control: public, max-age` on `/api/stats` and `/api/cards/facets` (`0` = no header) |
| `HEALTH_DB_TIMEOUT_SECONDS` | `2` | Query timeout of the `select 1` behind `GET /api/health` (200 `db:up` / 503 `db:down`) |

Every `/api/**` request writes one access-log line after it completes, e.g.
`access method=GET path=/api/cards status=200 duration_ms=12 request_id=… client_ip=…` (INFO;
`/api/health` at DEBUG). Headers, bodies and query values are never logged; `client_ip` honours
`API_TRUST_FORWARDED_FOR`.

## Docker (backend)

`backend/Dockerfile` builds a production image of the API: a JDK 21 stage runs
`./mvnw -DskipTests package` (tests run in CI), and a JRE 21 stage runs it as a non-root user
(uid 10001) on port 8080, with a `HEALTHCHECK` on `GET /api/health`. No configuration or secret
is baked in; `.env` files are excluded from the build context.

```bash
cd backend
docker build -t idea-finder-api .
docker run --rm -p 8080:8080 \
  -e DATABASE_URL -e DATABASE_USER -e DATABASE_PASSWORD \
  -e FRONTEND_ORIGIN=https://app.example.com \
  idea-finder-api
curl -i http://localhost:8080/api/health
```

Pass any variable from the table above with `-e` (or `--env-file`, kept outside the repo).
`SERVER_PORT` changes the port (the health check follows it); `JAVA_TOOL_OPTIONS` defaults to
`-XX:MaxRAMPercentage=75 -XX:+ExitOnOutOfMemoryError` and can be overridden. Behind a reverse
proxy that sets `X-Forwarded-For`, also pass `API_TRUST_FORWARDED_FOR=true`.

## Workflow

- Tickets live on the Supabase `project_board` table (keys like `IF-42`).
- Branch names: `<agent-slug>/<ticket_key>`; one commit per ticket, ticket key first.
- Never push to `main`; open an MR using the template in `.gitlab/merge_request_templates/`.
- An MR merges only after CI (GitHub Actions, reported back to GitLab) passes.
- Database changes are SQL files in `supabase/migrations/`, shipped in the same MR.
