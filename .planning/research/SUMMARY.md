# Project Research Summary

**Project:** GrantFlow
**Domain:** Government Grants Data-as-a-Service (DaaS) — multi-source ETL pipeline + API
**Researched:** 2026-03-24
**Confidence:** HIGH (stack and architecture verified against official sources and benchmarks; features verified against competitive landscape)

## Executive Summary

GrantFlow is a government grants data infrastructure product — not a grant management workflow tool. The expert pattern for this category is a three-layer architecture: Acquisition (scrapers + API adapters), Storage + Quality (PostgreSQL + normalization), and Delivery (FastAPI + API key auth). The existing FastAPI + SQLite MVP has the right bones but three structural blockers that prevent production readiness: SQLite's single-writer WAL model will serialize API reads during nightly bulk ingest of 80K+ rows, the ingestion pipeline has no scheduling or monitoring, and the API has no authentication or rate limiting. The good news is the architecture evolution is additive — no rewrite required.

The recommended approach is a phased migration that hardens existing infrastructure before expanding data coverage. PostgreSQL 16 replaces SQLite as the primary data store (SQLAlchemy models are already compatible — only `DATABASE_URL` and FTS query construction change). Prefect replaces manual CLI ingestion with a scheduled, observable pipeline. The API layer gets versioning, Pydantic response models, API key auth, and rate limiting before any paying customers integrate. State grant data — covering ~25 states with no centralized portal — is the primary market moat and must be operational before a paid tier launches. Federal-only data is available from government APIs for free; without state data, there is no compelling reason to pay.

The two critical risks are data reliability and launch timing. Silent pipeline failures (Grants.gov is mid-migration to a new API, SAM.gov has a hard 10 req/day public limit, state scrapers will break without warning) are existential in a DaaS product where freshness is the value proposition. The mitigation is mandatory: automated monitoring with per-source record count assertions and a `/v1/status` endpoint must exist before any external customers integrate. The second risk is GTM sequencing — launching paid access before state coverage is live means competing with free government APIs and losing.

## Key Findings

### Recommended Stack

The existing stack (FastAPI 0.135.2, SQLAlchemy 2.0.48, Pydantic 2.12.5, httpx 0.28.1, uvicorn) is correct and requires no changes. The additions are targeted gap-fillers, not replacements. See [STACK.md](.planning/research/STACK.md) for full analysis.

**Core technologies:**
- **PostgreSQL 16 + asyncpg 0.31.0**: Replace SQLite — eliminates WAL write contention during bulk ingest; tsvector GIN index replaces FTS5 with 5-10ms query times at 100K docs; native upsert eliminates N+1 SELECT-then-INSERT pattern. SQLAlchemy models are already compatible.
- **Alembic 1.14+**: Schema migration management — the `init_db()` pattern has no version tracking, no rollback, no CI safety. Required before any schema changes in production.
- **APScheduler 3.11.2** (not 4.x): In-process daily cron — no Redis or separate broker required; integrates via FastAPI lifespan. APScheduler 4.x is explicitly flagged as not production-safe by maintainers as of March 2026.
- **Scrapling 0.4+**: State portal scraping — adaptive selectors survive portal redesigns; built-in proxy rotation; Cloudflare bypass. Keep httpx for structured federal API calls (no scraping overhead needed).
- **Prefect (self-hosted)**: Pipeline orchestration — Python-native decorators, built-in retry/scheduling/alerting, no Kubernetes, lightweight for solo operator. Lower overhead than Airflow.
- **structlog 24.x**: Structured JSON logging — context binding per source (bind `source="grants_gov"` once, all log calls carry it); wraps stdlib so APScheduler/SQLAlchemy logs into same pipeline.
- **Gunicorn + Nginx + systemd**: Production serving — Gunicorn manages UvicornWorker processes (start with 3 workers on Hetzner CX22); Nginx handles SSL termination and request buffering.

### Expected Features

See [FEATURES.md](.planning/research/FEATURES.md) for full competitive landscape and feature dependency map.

**Must have (table stakes) — 70% already built:**
- Full-text keyword search with filters: agency, status, deadline, funding amount, eligibility type
- Opportunity detail page with link to original source
- Data freshness indicator — visible per record and in API responses
- Normalized eligibility codes — plain English applicant types, not raw CFDA codes
- Clean versioned API with OpenAPI docs and API key auth

**Should have (differentiators, Phase 2-3):**
- State grant aggregation (5-7+ states) — the primary moat; no competitor covers comprehensively
- Unified cross-source schema — one `/opportunities` endpoint spanning all sources
- Award history cross-reference — link open opportunities to USAspending historical awards by CFDA
- API-first developer experience with rate limiting tiers and developer docs

**Meaningful differentiation, Phase 3-4:**
- LLM-powered category tagging — government codes are unreliable; improves search precision
- Deadline/status change notifications — grants get amended without warning
- Funder profile pages — aggregated view of opportunities + awards by agency

**Defer to v2+:**
- Foundation/private grants (990 data) — Candid owns this with 40 years of data; 990 parsing is a $1M+ data operation
- Eligibility match scoring — requires organization profile data model; too early
- Real-time webhooks — government data refreshes daily at best; webhooks are premature complexity

**Anti-features (deliberately not building):**
- Grant application writing/AI drafting — Instrumentl raised $55M to own this; be the data layer, not the workflow
- Grant management / CRM — different market, deep nonprofit workflow knowledge required
- Mobile app — primary buyer (developer, researcher) is desktop-first
- International grants (non-US) — dilutes the US state data moat

### Architecture Approach

The target architecture separates three concerns with distinct operational profiles: Acquisition (I/O bound, fails often, needs retry), Storage + Quality (mixed read/write load, needs concurrent access), and Delivery (latency-sensitive, needs observability). All three can run on a single VPS initially — microservices before revenue create severe solo-operator overhead without benefit. See [ARCHITECTURE.md](.planning/research/ARCHITECTURE.md) for full component specs and data flow diagrams.

**Major components:**
1. **Source Adapters** (`grantflow/ingest/sources/`) — one module per external source; pure functions that yield normalized dicts; no DB access inside adapters (enables unit testing against fixtures)
2. **Pipeline Orchestrator** (Prefect) — schedules daily runs; handles retry, failure isolation, alerting; calls adapters and passes results to normalization layer
3. **Normalization + Quality Layer** (`grantflow/quality/`) — deduplication, status derivation, date normalization, cross-source entity resolution; runs as post-ingest pass, not mid-ingest
4. **Storage Layer** (PostgreSQL + Alembic) — owns all persistent state; adds `sources`, `pipeline_runs`, `data_quality_flags`, `api_keys` tables
5. **API Layer** (`grantflow/api/`) — versioned `/api/v1/` endpoints; API key validation; rate limiting via slowapi; Pydantic v2 response models replacing hand-rolled `_opportunity_to_dict()`; `/api/v1/status` health endpoint
6. **Web UI** (`grantflow/web/`) — thin layer over shared `build_opportunity_query()` helper; no duplicated search logic
7. **Monitoring Surface** — pipeline run results in `pipeline_runs` table; per-source count anomaly detection; Prefect notification hooks for failure alerts

### Critical Pitfalls

See [PITFALLS.md](.planning/research/PITFALLS.md) for full analysis including phase-specific warnings.

1. **Grants.gov API migration will break your pipeline silently** — The XML bulk extract is being deprecated in favor of a new REST API that is still "subject to change." Add per-run record count assertions (±20% threshold) and RSS monitoring before any pipeline hardening. Plan dual-source: keep XML until REST is proven stable for 30+ days.

2. **Selling before the pipeline is proven reliable** — No automated ingestion, no monitoring, no health check endpoint currently exists. A DaaS product that delivers stale data is worse than no product. Monitoring and daily automated pipeline are prerequisites to GTM, not concurrent with it.

3. **State scraper rot destroys the moat silently** — State portals redesign without notice; a scraper that returns 0 records looks the same as one that returns valid data. Per-source count assertions must fire an alert on zero-record runs. Budget 2-4 hrs/month per active state for maintenance.

4. **Cross-source duplicate records erode search quality** — The same grant appears on Grants.gov, SBIR, and potentially state portals. Without a canonical dedup layer, search shows the same opportunity 3x with inconsistent field values. Must be solved before public API launch.

5. **SAM.gov 10 req/day public limit is a hard wall** — Naive bulk sync hits the cap in the first API call. Design SAM.gov ingest as incremental (modified-since-last-run), cache all responses, and apply for highest rate limit tier from registration day one.

## Implications for Roadmap

Based on combined research, the natural build sequence is driven by dependency chains: PostgreSQL unblocks concurrent ingest + API reads; Prefect unblocks reliable daily data; API hardening unblocks monetization; state data unblocks paid GTM.

### Phase 1: Foundation — Database and API Hardening

**Rationale:** SQLite is the single most urgent blocker. Every other phase depends on a database that can handle concurrent reads during nightly ingest. This phase also establishes the API contract (versioning, Pydantic models, shared query builder) that all future features extend.
**Delivers:** Production-capable database; stable API schema; migration tooling for safe schema evolution
**Addresses:** Full-text search filters (funding amount, eligibility type) currently missing from UI; data freshness timestamps surfaced to API
**Avoids:** SQLite write contention (Pitfall 7); breaking API changes post-integration (Pitfall 6)
**Stack:** PostgreSQL 16 + asyncpg, Alembic, Pydantic v2 response models, shared `build_opportunity_query()`
**Research flag:** Standard patterns — well-documented SQLAlchemy migration path; skip research-phase

### Phase 2: Pipeline Hardening — Automated Ingestion and Monitoring

**Rationale:** Daily automated pipeline with monitoring is a prerequisite to any paid customer integrating. Silent failures in a DaaS product are existential. This phase must complete before GTM activities begin.
**Delivers:** Automated daily ingestion; per-source health monitoring; `/v1/status` endpoint; failure alerting
**Addresses:** Normalized eligibility codes; data freshness per source; deduplication layer
**Avoids:** Silent pipeline failure (Pitfall 5); Grants.gov migration breaking silently (Pitfall 1); cross-source duplicates (Pitfall 4)
**Stack:** Prefect (self-hosted), APScheduler 3.11, structlog, source adapter isolation
**Research flag:** Prefect integration patterns are well-documented; Grants.gov migration monitoring needs ongoing attention — track RSS feed

### Phase 3: Production API — Auth, Rate Limiting, Developer Experience

**Rationale:** Cannot charge customers without API key auth, rate limiting, and reliable versioned responses. This phase converts the functional API into a monetizable product.
**Delivers:** API key issuance and management; tiered rate limiting; OpenAPI docs; canonical field schema
**Addresses:** Clean API with developer docs (table stakes); unified cross-source schema (differentiator)
**Avoids:** API keys in plaintext (Pitfall: store SHA-256 hashes only); raw government field names in API (Pitfall 13)
**Stack:** slowapi, `api_keys` table, Pydantic v2 response models, `/api/v1/` versioning
**Research flag:** Standard patterns — skip research-phase; slowapi is the documented FastAPI rate limiting approach

### Phase 4: State Data — Build the Moat

**Rationale:** Federal-only data competes with free government APIs. The moat is state grant data that does not exist in unified form anywhere. This phase must complete before paid tier launch.
**Delivers:** 5-10 state portal scrapers; state data surfaced in search and API; public source coverage status page
**Addresses:** State grant aggregation (primary differentiator); unified cross-source schema
**Avoids:** Launching with only federal data (Pitfall 9); scraper rot without monitoring (Pitfall 3); state-level legal ambiguity (Pitfall 12 — ToS/robots.txt review per state before scraping)
**Stack:** Scrapling 0.4+, datacenter proxies (Webshare/Decodo), per-source Prefect tasks with exponential backoff retry
**Research flag:** Needs research-phase — proxy strategy per state portal, legal review per state, selector strategy per CMS type

### Phase 5: GTM and Data Enrichment

**Rationale:** With state data live and pipeline proven reliable, the product is ready for paid customers. Pricing model must be validated with 5+ buyer conversations before Stripe integration. Enrichment (LLM tagging, award cross-reference) makes the data more valuable without requiring new sources.
**Delivers:** Paid tier launch; pricing validated; award cross-reference (USAspending join); LLM category tagging as separate enrichment pipeline stage
**Addresses:** Award history cross-reference (Tier 1 differentiator); LLM tagging (Tier 2 differentiator)
**Avoids:** Pricing on call volume when buyers value coverage (Pitfall 8); LLM enrichment baked into ingest pipeline (Pitfall 10)
**Research flag:** Pricing model needs GTM validation conversations before implementation; LLM enrichment pipeline design needs research-phase

### Phase Ordering Rationale

- PostgreSQL must precede Prefect — the pipeline orchestrator needs a database that handles concurrent reads during its write operations
- Pipeline monitoring must precede API key issuance — if a customer integrates before monitoring is live, a silent failure causes churn with no visibility
- State data must precede paid GTM — federal-only data has no competitive moat against free government APIs
- Enrichment (LLM tagging, eligibility scoring) must be a separate pipeline stage, never coupled to raw ingest — different failure characteristics, different operational cadence
- Do not add microservices until a specific bottleneck demands it — single VPS path is viable to $10K MRR

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (State Data):** Each state portal requires individual research — ToS/robots.txt review, CMS identification, scraper selector strategy, proxy needs. Scrapling's adaptive selectors reduce but do not eliminate this work. Budget one research spike per state cohort (e.g., top-5 states by grant volume).
- **Phase 5 (Enrichment):** LLM enrichment pipeline architecture — batching strategy, cost per record, re-processing on prompt change, model versioning. Needs a design spike before implementation.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** PostgreSQL + Alembic + SQLAlchemy migration is one of the most documented Python patterns. No research needed.
- **Phase 2 (Pipeline):** Prefect self-hosted setup and FastAPI integration is well-documented with multiple 2025-2026 guides.
- **Phase 3 (Production API):** slowapi + FastAPI API key middleware is standard; SHA-256 key hashing is a known pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | PostgreSQL, Alembic, asyncpg verified against official docs and 2026 benchmarks; APScheduler 4.x warning verified against maintainer docs; Scrapling v0.4 confirmed on PyPI |
| Features | MEDIUM-HIGH | Competitive landscape verified across multiple sources; user pain points from review aggregators; market gap analysis is inference from pricing/coverage gaps |
| Architecture | HIGH | Current codebase constraints verified from code audit (CONCERNS.md); component patterns from corroborated DaaS sources; Prefect vs Airflow comparison from multiple 2025-2026 sources |
| Pitfalls | HIGH for scraper/pipeline pitfalls | Grants.gov migration status confirmed from official blog; SAM.gov limits confirmed; legal analysis cites specific statute; MEDIUM for GTM/pricing pitfalls (less post-mortem literature) |

**Overall confidence:** HIGH

### Gaps to Address

- **Scrapling production maturity:** v0.4 released February 2026; community adoption is growing but the library is newer than alternatives. Validate with a proof-of-concept scraper on 2-3 state portals before committing to it as the primary scraping layer. If it fails, Playwright + custom proxy rotation is the fallback.
- **Prefect vs APScheduler:** ARCHITECTURE.md recommends Prefect for orchestration; STACK.md recommends APScheduler for scheduling. These are not mutually exclusive — APScheduler can trigger Prefect flows, or Prefect's built-in scheduling can replace APScheduler entirely. Clarify the integration pattern before Phase 2 implementation.
- **Datacenter proxy viability per state:** Research classifies government portals as Tier 1 (minimal bot protection), but individual state portals may use Cloudflare or Akamai. Validate proxy tier needs per state before scaling scraper count.
- **Grants.gov REST API stability:** The new `simpler.grants.gov` REST API launched March 2025 and is labeled "subject to change." Monitor monthly; do not migrate off XML bulk extract until REST has been stable for 30+ days.
- **Pricing model:** Not validated with actual buyers. The dataset-tier model (federal-only vs. federal+state, by refresh frequency) is the research recommendation, but pricing must be validated with 5+ buyer conversations before Stripe implementation.

## Sources

### Primary (HIGH confidence)
- [SQLite in Production benchmarks](https://yyhh.org/blog/2026/01/sqlite-in-production-not-so-fast-for-complex-queries/) — 3x worse median query, 9 timeouts at comparable dataset
- [Neon: PostgreSQL FTS vs Elasticsearch](https://neon.com/blog/postgres-full-text-search-vs-elasticsearch) — 5-10ms FTS at 100K rows with GIN index
- [asyncpg benchmark](https://dasroot.net/posts/2026/02/python-postgresql-sqlalchemy-asyncpg-performance-comparison/) — 2,800 ops/sec vs 1,450 for sync ORM
- [APScheduler PyPI + migration docs](https://pypi.org/project/APScheduler/) — 3.11.2 stable; 4.x explicitly "do not use in production"
- [FastAPI official deployment docs](https://fastapi.tiangolo.com/deployment/) — Gunicorn + UvicornWorker pattern
- [Grants.gov API Resources](https://www.grants.gov/api) — migration status confirmed
- [SAM.gov rate limits](https://govconapi.com/sam-gov-rate-limits-reality) — 10 req/day public, 1,000/day registered
- [17 U.S.C. § 105](https://www.law.cornell.edu/uscode/text/17/105) — federal works public domain; state works not covered
- GrantFlow CONCERNS.md — internal codebase audit (2026-03-24)

### Secondary (MEDIUM confidence)
- [Scrapling v0.4 on PyPI + Apify blog](https://use-apify.com/blog/scrapling-python-web-scraping-framework) — February 2026, production validation claims
- [Prefect vs Airflow comparison](https://www.zenml.io/blog/orchestration-showdown-dagster-vs-prefect-vs-airflow) — solo operator overhead analysis
- [Proxy classification guide](https://use-apify.com/blog/proxy-rotation-web-scraping-guide) — government portals as Tier 1
- [SafeGraph DaaS Bible](https://www.safegraph.com/blog/data-as-a-service-bible-everything-you-wanted-to-know-about-running-daas-companies) — DaaS pricing and GTM patterns
- [Instrumentl Capterra Reviews 2026](https://www.capterra.com/p/233384/Instrumentl/reviews/) — user pain points
- Competitive pricing: Instrumentl ($162-499/mo), GrantWatch ($22-249/mo), Candid FDO ($35-219/mo), GovWin IQ ($2K-45K/yr)

### Tertiary (LOW confidence — needs validation)
- Pricing model validation — inference from competitive landscape; not validated with actual buyers
- State portal legal analysis per state — framework from statute and case law; per-state review still needed

---
*Research completed: 2026-03-24*
*Ready for roadmap: yes*
