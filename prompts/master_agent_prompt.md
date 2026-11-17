# IDEA FINDER — PRODUCT SPECIFICATION & SYSTEM DIRECTIVE
Version 3 · MVP phase · Shared by every agent

## 1. Mission
Idea Finder is an automated market-intelligence platform. It ingests unstructured user feedback, technical discussions, and low-rating product reviews, and turns them into validated, evidence-backed software opportunities ("Opportunity Cards"), with a focus on high-intent B2B and developer friction.

Personas:
1. **Indie builders & solopreneurs** — want validated, high-value micro-SaaS ideas and narrow MVP wedges.
2. **Product managers & innovation labs** — want continuous market-drift analysis, competitor review monitoring, and feature-demand validation.

## 2. Data sources (phased)
**Phase 1 — MVP (build now):**
- **Reddit** — niche subreddits: raw workflows, technical complaints, "how do I fix X?" threads. Official Reddit API (OAuth) only; access approval is pending, so build and test against recorded fixtures until keys arrive.
- **GitHub Issues & Discussions** — workarounds, broken integrations, popular feature requests on open-source tools. Official GitHub API with a token only.
- **Hacker News** — "Ask HN" threads and comments: founder and developer pain points. Official HN API and Algolia HN Search API (no key).
- **Stack Exchange** (Stack Overflow, Server Fault, Super User, etc.) — recurring "how do I…" questions about broken tools and workarounds. Official Stack Exchange API with `STACKEXCHANGE_KEY`; respect its quota and backoff.

**Phase 2 — planned, NOT in v1:**
- **G2 & Capterra (1–3 star reviews)** — high-budget enterprise complaints and willingness-to-pay signals. Only through an official API or licensed data partner; never scraped. Design code so a new source is a pluggable adapter, but do not build G2/Capterra adapters until the founder opens a ticket for it.

**Phase 3 — source discovery:** a meta-agent that suggests new sources (developer forums, app-store reviews, launch sites). Suggestions only; no new source is ingested without founder approval.

## 3. Opportunity Card — the 7-point schema
Every card must have all seven fields (stored in `opportunity_cards`):

| # | Field | Column | Rules |
|---|---|---|---|
| — | Title | `title` | Short, descriptive, auto-generated |
| 1 | Problem Statement | `problem_statement` | 1–2 factual sentences describing the core pain |
| 2 | Trigger Context & Frequency | `trigger_context` | When it occurs; mention count, velocity, source spread |
| 3 | Market Size / Segment | `market_size` | Persona, company size, industry |
| 4 | Duct-Tape Solutions | `duct_tape_solutions` | How users cope today (CSV exports, Zapier, scripts…) |
| 5 | Economic Intent | `economic_intent` | `High` / `Medium` / `Low` / `Unspecified` |
| 6 | MVP Wedge | `mvp_wedge` | Smallest standalone build, written as modular engineering scope |
| 7 | Confidence Score | `confidence_score` | 1–100, from cross-source validation, urgency, budget signal |

Plus provenance: `source_platform` (`reddit`, `github`, `hackernews`, `stackexchange`, `g2`, `capterra`, `other`), `source_url`, `raw_content_snippet`, `is_b2b_filtered`, `embedding` (vector 1536) and `embedding_model`.

## 4. Tiers & feature gating (planned — not built yet)
Authentication, billing and tier enforcement do not exist yet. Treat them as future features, not as bugs, until tickets for them are Deployed.
- **Free:** Reddit, GitHub, Hacker News, Stack Exchange; 5 manual searches/month; card shows Problem Statement + Duct-Tape Solutions only.
- **Pro ($29–49/mo):** all Phase 1 sources (+ G2/Capterra once Phase 2 ships); full card; weekly trend digests; niche monitoring.
- **Enterprise / Studio ($199+/mo):** all sources + custom competitor sources; Slack webhooks and instant alerts; JSON/CSV export; team boards.

## 5. Non-negotiable product rules
- **No speculative ideas.** Every card must be anchored in real ingested data; never invent problems, counts or quotes.
- **B2B focus.** Prefer business loss, wasted developer hours and operational friction over consumer annoyances.
- **Actionable wedges.** MVP Wedges must be concrete enough for an engineer to turn into services or components.
- **Respectful ingestion.** Official APIs only, honor rate limits and terms of service, no user-agent spoofing or anti-bot evasion.
