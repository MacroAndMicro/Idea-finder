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

## Configuration

Secrets and settings come only from environment variables. Copy `.env.example` to `.env`
and fill it in; the file lists every variable by name. Never commit `.env` or any value.

## Workflow

- Tickets live on the Supabase `project_board` table (keys like `IF-42`).
- Branch names: `<agent-slug>/<ticket_key>`; one commit per ticket, ticket key first.
- Never push to `main`; open an MR using the template in `.gitlab/merge_request_templates/`.
- An MR merges only after CI (GitHub Actions, reported back to GitLab) passes.
- Database changes are SQL files in `supabase/migrations/`, shipped in the same MR.
