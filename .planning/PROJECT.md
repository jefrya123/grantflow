# GrantFlow

## What This Is

A unified government grants and contracts data platform that aggregates fragmented federal and state grant data into one clean, searchable API and search tool. Wraps broken government APIs (Grants.gov, SAM.gov, USAspending, SBIR.gov) and underserved state grant portals into a developer-friendly data product that people actually pay for.

## Core Value

Make government grant data discoverable, clean, and instantly accessible — the data infrastructure layer that every grant-related product needs but nobody wants to build and maintain.

## Requirements

### Validated

- ✓ Grants.gov XML bulk extract ingestion (81,856 opportunities) — existing
- ✓ USAspending API integration (5,000 historical awards) — existing
- ✓ Unified SQLite schema with FTS5 full-text search — existing
- ✓ FastAPI REST API with search, detail, stats endpoints — existing
- ✓ Server-rendered search UI with filters — existing
- ✓ Date normalization and status derivation — existing

### Active

- [ ] Production-grade data pipeline (reliable, automated, monitored)
- [ ] Comprehensive federal data coverage (fix SBIR, add SAM.gov contracts, cross-reference awards)
- [ ] State grant data aggregation (top 10 states — the competitive moat)
- [ ] Production API (rate limiting, API keys, versioning, error handling, docs)
- [ ] Data quality and enrichment (dedup, LLM categorization, eligibility parsing)
- [ ] Go-to-market validation (landing page, pricing, demand signals)
- [ ] Search experience that helps people actually find grants they qualify for

### Out of Scope

- Stripe/billing integration — deploy and validate demand first, monetize later (learned from AgentGrade)
- User accounts and auth — keep it open/simple until proven demand
- Grant application writing/AI — we're the data layer, not the workflow tool (Instrumentl's territory)
- Foundation/private grants (990 data) — defer until government data is solid
- Mobile app — web-first
- Real-time notifications/webhooks — batch/daily refresh is fine for v1

## Context

- **Market validated:** Instrumentl at $50M+ ARR proves grant data demand. No API-first competitor exists at the $49-499/mo price point.
- **Government APIs are broken:** Grants.gov detail endpoint is literally down. SAM.gov has 10 req/day limit. No unified schema.
- **State data is the moat:** ~25 states have no centralized grants portal. Aggregating this creates data that doesn't exist anywhere else.
- **Existing MVP:** Working ingestion pipeline, 81K opportunities, 5K awards, API + search UI. Needs hardening, not rebuilding.
- **AgentGrade lessons:** Don't over-invest in billing/auth before validating demand. Ship the core value first.
- **Scrapling available:** Adaptive web scraping framework with Cloudflare bypass for state portal scraping.
- **Ruflo planned:** Agent orchestration for running daily pipeline, coordinating scraper agents.

## Constraints

- **Stack**: Python 3.12+ / FastAPI / SQLAlchemy — existing, research may recommend upgrades (e.g., PostgreSQL for production scale)
- **Solo operator**: Must be low-maintenance once running — scrapers can't need daily babysitting
- **Budget**: Minimal infra spend until revenue validates — VPS hosting (Hetzner), no expensive managed services
- **Legal**: Only scrape public government data — zero legal risk tolerance
- **Data freshness**: Daily refresh is sufficient — not real-time

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Government grants as first data product | Zero legal risk, broken existing APIs, proven demand ($50M+ ARR competitor), massive federal spending tailwind | — Pending |
| Skip Stripe until demand validated | AgentGrade taught us billing complexity before PMF is wasted effort | — Pending |
| State data as competitive moat | Federal data is freely available; state aggregation creates defensible data that doesn't exist elsewhere | — Pending |
| Research-driven GTM | Let research determine buyer persona (B2B API vs direct users) rather than guessing | — Pending |
| Research-driven tech decisions | Let research recommend stack upgrades vs. premature optimization | — Pending |

---
*Last updated: 2026-03-29 — Phase 12 complete (Fund-Your-Fix Web Page SEO)*
