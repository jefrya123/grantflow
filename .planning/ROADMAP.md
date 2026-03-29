# Roadmap: GrantFlow

## Overview

GrantFlow hardens an existing MVP (81K opportunities, working API, search UI) into a production DaaS product. Only Phase 1 (PostgreSQL migration) is a true serial blocker. After Phase 1, work fans out into three parallel tracks — pipeline hardening, API key infrastructure, and data quality normalization — that converge before the state scraper and web UI work begins. This structure maximizes parallel execution: four of five waves contain work that can be dispatched to concurrent agents.

**Wave structure:**
- Wave 1 (Phase 1): PostgreSQL migration — unblocks everything
- Wave 2 (Phases 2, 3, 4): Pipeline + API keys + Data quality — all depend only on Wave 1, run in parallel
- Wave 3 (Phases 5, 6): State scraper build-out + advanced API/Web — depend on Wave 2
- Wave 4 (Phase 7): GTM launch + LLM enrichment — depends on Wave 3
- Wave 5 (Phases 8, 9): Gap closure — pipeline/data cleanup + API/feature polish (parallel)
- Wave 6 (Phases 11, 12): Fund Your Fix — ADA compliance grant tagging + web page (serial)

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

## Phases

- [x] **Phase 1: Foundation** - Migrate SQLite to PostgreSQL with Alembic and harden the API contract [WAVE 1 — serial blocker] (completed 2026-03-24)
- [ ] **Phase 2: Pipeline Hardening** - Automate all federal ingestion with daily scheduling and monitoring [WAVE 2 — parallel]
- [x] **Phase 3: API Key Infrastructure** - Self-serve API keys with tiered rate limiting and versioned stable schema [WAVE 2 — parallel] (completed 2026-03-24)
- [ ] **Phase 4: Data Quality** - Normalize eligibility codes, agency names, dates, amounts, and deduplicate across sources [WAVE 2 — parallel]
- [x] **Phase 5: State Data** - Build and operate scrapers for 5+ state grant portals (the competitive moat) [WAVE 3 — parallel] (completed 2026-03-24)
- [ ] **Phase 6: Advanced API + Web UI** - Full-featured search UI, opportunity detail, bulk export, and developer experience polish [WAVE 3 — parallel]
- [x] **Phase 7: GTM + Enrichment** - Launch landing page, pricing, API playground, usage analytics, and LLM categorization [WAVE 4] (completed 2026-03-24)
- [x] **Phase 8: Pipeline & Data Cleanup** - Remove FTS5 remnants, wire SAM.gov normalizers, clean dead code [WAVE 5 — gap closure] (completed 2026-03-24)
- [x] **Phase 9: API & Feature Polish** - Tier-aware rate limits, export topic filter, canonical_id exposure, enrichment scheduler [WAVE 5 — gap closure] (completed 2026-03-24)
- [ ] **Phase 11: ADA Compliance Grant Tagging & API** - Tag/categorize ADA-related grants and expose via dedicated API endpoint with municipality cross-link support [WAVE 6 — Fund Your Fix]
- [ ] **Phase 12: Fund Your Fix Web Page & SEO** - Public /fund-your-fix page showing ADA grants with deadlines, award amounts, municipality filtering, and full SEO [WAVE 6 — Fund Your Fix]

## Phase Details

### Phase 1: Foundation
**Goal**: The application runs on PostgreSQL with schema migration tooling, full-text search, and a health endpoint — providing a stable, production-capable base for all subsequent work
**Depends on**: Nothing (Wave 1 — serial blocker)
**Wave**: 1
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04
**Success Criteria** (what must be TRUE):
  1. The application connects to PostgreSQL in production via environment config — SQLite is no longer used
  2. Full-text search queries run against a tsvector GIN index and return results within acceptable latency
  3. Schema changes can be applied and rolled back via Alembic migrations without manual SQL
  4. The health endpoint returns current pipeline freshness timestamps and record counts per source
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Install deps (asyncpg, psycopg2-binary, alembic), reconfigure database.py for PostgreSQL/SQLite dual-dialect, initialize Alembic with initial schema migration
- [ ] 01-02-PLAN.md — Replace FTS5 virtual table with tsvector column + GIN index + trigger via Alembic migration 0002; update API and web routes to use to_tsquery()
- [ ] 01-03-PLAN.md — Add GET /api/v1/health endpoint (pipeline freshness + record counts per source); create tests/conftest.py and first test suite

### Phase 2: Pipeline Hardening
**Goal**: All federal data sources ingest automatically on a daily schedule with monitoring that detects and alerts on stale or broken data before any customer notices
**Depends on**: Phase 1
**Wave**: 2 (parallel with Phases 3 and 4)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, PIPE-08
**Success Criteria** (what must be TRUE):
  1. Grants.gov, USAspending, SBIR, and SAM.gov all run on automated daily schedule without manual intervention
  2. Pipeline logs show records added, updated, and failed per source per run — visible in structured logs
  3. An alert fires within 48 hours when any source has not updated (stale data detection)
  4. Grants.gov ingestion works from both XML extract and the new REST API so migration can happen safely
  5. Opportunities are cross-referenced to historical USAspending awards via CFDA/ALN numbers
**Plans**: 5 plans

Plans:
- [ ] 02-01-PLAN.md — PipelineRun model + Alembic migration 0003; structlog setup with configure_structlog() and bind_source_logger()
- [ ] 02-02-PLAN.md — APScheduler daily cron at 02:00 UTC in app lifespan; harden all three ingesters (PipelineRun writes, structlog, SBIR retry, USAspending incremental, bug fixes)
- [ ] 02-03-PLAN.md — SAM.gov incremental ingestor: rate-limit-aware, skips cleanly without API key, integrated as pipeline step 4
- [ ] 02-04-PLAN.md — Grants.gov dual-source: REST API primary path + XML fallback; GRANTS_GOV_USE_REST flag for migration testing
- [ ] 02-05-PLAN.md — Stale data monitor (48h alert, email on GRANTFLOW_ALERT_EMAIL); CFDA normalization and cross-source award linking; /api/v1/health freshness extension

### Phase 3: API Key Infrastructure
**Goal**: Developers can self-serve API keys, the API is versioned at /api/v1/ with stable schema, and rate limiting enforces tier boundaries — the foundation for monetization
**Depends on**: Phase 1
**Wave**: 2 (parallel with Phases 2 and 4)
**Requirements**: API-01, API-02, API-03, API-04, API-07
**Success Criteria** (what must be TRUE):
  1. A developer can generate an API key via the self-serve endpoint — plaintext shown once, SHA-256 hash stored
  2. Requests with a valid API key succeed; requests without one are rejected with a consistent error response
  3. Rate limits fire appropriately per key tier (free/starter/growth) and return a meaningful 429 response
  4. All API endpoints are accessible under /api/v1/ with stable field names
  5. OpenAPI docs are auto-generated, accurate, and accessible without an API key
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — ApiKey model, Alembic migration 0003, POST /api/v1/keys endpoint, consistent error response shape
- [ ] 03-02-PLAN.md — X-API-Key auth middleware, slowapi rate limiting, protect data endpoints (free=1000/day)
- [ ] 03-03-PLAN.md — Pydantic response models replacing _opportunity_to_dict(), response_model= on all routes, OpenAPI metadata

### Phase 4: Data Quality
**Goal**: All data served through the API and web UI uses normalized, human-readable field values — no raw government codes, no inconsistent agency names, no invalid award amounts
**Depends on**: Phase 1
**Wave**: 2 (parallel with Phases 2 and 3)
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-05, QUAL-06
**Success Criteria** (what must be TRUE):
  1. Eligibility codes in API responses and search results are human-readable categories (not raw CFDA codes)
  2. Agency names are consistent across Grants.gov, USAspending, SBIR, and SAM.gov sources
  3. Duplicate opportunities detected across sources are merged to a single canonical record
  4. All date fields are ISO 8601 across all sources — no mixed formats
  5. Award amounts with floor > ceiling or negative values are flagged and excluded from clean data set
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — Create normalization layer (dates, eligibility codes, agency names, amount validation) and wire into all ingest modules
- [ ] 04-02-PLAN.md — Add canonical_id for cross-source deduplication via Alembic migration and dedup module

### Phase 5: State Data
**Goal**: At least 5 state grant portals are scraped on a regular schedule, normalized into the unified schema, and monitored so breakage is detected automatically — creating data that does not exist anywhere else
**Depends on**: Phase 2, Phase 4
**Wave**: 3 (parallel with Phase 6)
**Dependency rationale**: Needs Phase 2 pipeline infrastructure for scheduling/monitoring; needs Phase 4 normalization for unified schema integration
**Requirements**: STATE-01, STATE-02, STATE-03, STATE-04, STATE-05
**Success Criteria** (what must be TRUE):
  1. State grant opportunities from at least 5 states appear in search results alongside federal data
  2. Each state source has passed a ToS/robots.txt/open-data legal review before data is collected
  3. An alert fires when any state scraper returns zero records (distinguishes breakage from legitimately empty results)
  4. State data refreshes automatically on at least a weekly schedule without manual intervention
**Plans**: 3 plans

Plans:
- [ ] 05-01-PLAN.md — BaseStateScraper infrastructure, test scaffolds, legal review for 5 portals
- [ ] 05-02-PLAN.md — Implement 5 state scrapers (CA CKAN, NY Socrata, IL CKAN, TX Socrata, CO Scrapling)
- [ ] 05-03-PLAN.md — Monitoring (zero-record alerts, per-source stale thresholds), weekly scheduling, run_state.py orchestrator

### Phase 6: Advanced API + Web UI
**Goal**: The API delivers a complete developer experience with bulk export, agency endpoints, and linked historical awards; the web UI gives end users full search, filtering, discovery, and stats — all over clean normalized data
**Depends on**: Phase 3, Phase 4
**Wave**: 3 (parallel with Phase 5)
**Dependency rationale**: Needs Phase 3 API key auth for endpoint protection; needs Phase 4 normalized data for clean display
**Requirements**: API-05, API-06, API-08, WEB-01, WEB-02, WEB-03, WEB-04
**Success Criteria** (what must be TRUE):
  1. The web search page supports filtering by status, agency, category, eligibility, dates, and award range
  2. An opportunity detail page shows linked historical awards from USAspending
  3. Opportunities closing within 30 days display a "closing soon" badge
  4. A stats dashboard shows total opportunities by source, agency, and closing soon counts
  5. A bulk export endpoint returns search results as CSV or JSON for any valid API key
  6. An agencies endpoint returns a list of agencies with their opportunity counts
**Plans**: 2 plans

Plans:
- [ ] 06-01-PLAN.md — Shared query builder, bulk export endpoint (CSV/JSON), AgencyResponse schema, linked awards test coverage
- [ ] 06-02-PLAN.md — Search page full filters, closing-soon badge, stats dashboard page, nav update

### Phase 7: GTM + Enrichment
**Goal**: The product has a public-facing landing page, pricing page, and interactive API playground that generate demand signals, backed by usage analytics and LLM-powered topic categorization that improves search precision
**Depends on**: Phase 5, Phase 6
**Wave**: 4
**Dependency rationale**: Needs Phase 5 state data live (competitive moat required before paid GTM); needs Phase 6 API for the playground and analytics instrumentation
**Requirements**: QUAL-04, GTM-01, GTM-02, GTM-03, GTM-04
**Success Criteria** (what must be TRUE):
  1. A visitor to the landing page understands the product value proposition and can reach the pricing page in one click
  2. A developer can try a live API query from the playground without creating an account
  3. Pricing tiers based on data coverage (not call volume) are publicly displayed
  4. Every API endpoint hit, search query, and API key usage is tracked in analytics
  5. Opportunities carry LLM-assigned topic/sector tags that are searchable and filterable
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md — GTM pages (landing, pricing, playground), usage analytics middleware with api_events table, demo key seed script
- [ ] 07-02-PLAN.md — LLM topic tagging with instructor + OpenAI, topic_tags column, API/web search filter integration

### Phase 8: Pipeline & Data Cleanup
**Goal**: Remove FTS5 write path remnants, wire SAM.gov ingestor through the normalization layer, and clean up dead code — eliminating crash risks and ensuring all data sources produce consistent normalized output
**Depends on**: Phase 7
**Wave**: 5 (gap closure)
**Gap Closure:** Closes gaps from v1.0 audit
**Requirements**: FOUND-02, QUAL-01, QUAL-02, QUAL-05, QUAL-06
**Success Criteria** (what must be TRUE):
  1. No FTS5 virtual table references remain in application code — ingestion runs cleanly on PostgreSQL
  2. SAM.gov records have normalized dates (ISO 8601), agency names, eligibility codes, and validated award amounts
  3. No unused normalizer imports exist in any ingestor file
**Plans**: 2 plans

Plans:
- [ ] 08-01-PLAN.md — Fix normalize_date() timezone gap, remove sbir.py dead import, verify FTS5 cleanup
- [ ] 08-02-PLAN.md — Wire SAM.gov ingestor through shared normalization layer, remove _parse_sam_date()

### Phase 9: API & Feature Polish
**Goal**: Complete the API contract (tier-aware rate limits, topic filter on export, canonical_id in responses) and wire LLM enrichment into the scheduler so topic tags populate automatically
**Depends on**: Phase 8
**Wave**: 5 (gap closure, parallel with Phase 8)
**Gap Closure:** Closes gaps from v1.0 audit
**Requirements**: API-02, API-05, QUAL-03, QUAL-04
**Success Criteria** (what must be TRUE):
  1. Rate limits vary by API key tier (free=1000, starter=10000, growth=100000 per day)
  2. Bulk export endpoint supports ?topic= filter matching the search endpoint
  3. canonical_id is included in OpportunityResponse API schema
  4. LLM enrichment runs on a daily APScheduler job (gated on OPENAI_API_KEY)
**Plans**: 2 plans

Plans:
- [ ] 09-01-PLAN.md — Tier-aware rate limits on all API endpoints + export topic filter
- [ ] 09-02-PLAN.md — canonical_id in OpportunityResponse + enrichment APScheduler job

### Phase 11: ADA Compliance Grant Tagging & API
**Goal**: Identify and tag grants related to ADA remediation, transit accessibility, and disability compliance in the database; expose them via a dedicated API endpoint with optional municipality cross-link filtering
**Depends on**: Phase 10
**Wave**: 6 (Fund Your Fix — serial)
**Requirements**: ADA-01, ADA-02, ADA-03
**Success Criteria** (what must be TRUE):
  1. An `ada_tags` JSON column (or equivalent tag mechanism) is populated for all grants matching ADA/accessibility keyword criteria across title, description, and agency fields
  2. GET /api/v1/opportunities/ada-compliance returns paginated results with title, deadline, award_min, award_max, source, apply_url, and canonical_id
  3. Endpoint accepts optional `?municipality=<slug>` query param and returns grants relevant to that municipality's violation type profile
  4. Endpoint is documented in OpenAPI and returns proper 200/422 responses
  5. At least the DOT FTA "All Stations Access" grant (deadline 2026-05-01) appears in results
**Plans**: 2 plans

Plans:
- [ ] 11-01-PLAN.md — ADA keyword tagger backfill script (ada_tagger.py) with curated keyword matching + unit tests
- [ ] 11-02-PLAN.md — GET /api/v1/opportunities/ada-compliance public endpoint with municipality filtering + integration tests

### Phase 12: Fund Your Fix Web Page & SEO
**Goal**: Public-facing page at /fund-your-fix displays curated ADA compliance grants with clear deadlines and award amounts, municipality filtering, and full SEO metadata following existing web/routes.py patterns
**Depends on**: Phase 11
**Wave**: 6 (Fund Your Fix — serial)
**Requirements**: ADA-04, ADA-05, ADA-06
**Success Criteria** (what must be TRUE):
  1. /fund-your-fix renders a page listing ADA compliance grants sorted by deadline proximity
  2. Each grant shows title, deadline (formatted), award range, agency, and apply link
  3. Page accepts ?municipality=<slug> query param and shows relevant grants for that municipality
  4. JSON-LD structured data (ItemList schema) is present following the existing web/routes.py pattern
  5. OpenGraph (og:title, og:description, og:image) and Twitter Card meta tags are present
  6. DOT FTA "All Stations Access" grant is featured with its 2026-05-01 deadline prominently highlighted
  7. /ada-grants redirects to /fund-your-fix (or is an alias)
**Plans**: 0 plans

## Progress

**Execution Order (wave-parallel):**

```
Wave 1:  Phase 1
                  ↓
Wave 2:  Phase 2 ║ Phase 3 ║ Phase 4   (all depend only on Phase 1)
                  ↓           ↓
Wave 3:  Phase 5 (needs 2+4) ║ Phase 6 (needs 3+4)
                  ↓
Wave 4:  Phase 7 (needs 5+6)
                  ↓
Wave 5:  Phase 8 ║ Phase 9   (gap closure — parallel)
```

| Phase | Wave | Depends On | Plans Complete | Status | Completed |
|-------|------|------------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete   | 2026-03-24 | Complete | 2026-03-24 |
| 2. Pipeline Hardening | 5/5 | Complete   | 2026-03-24 | Complete | 2026-03-24 |
| 3. API Key Infrastructure | 3/3 | Complete   | 2026-03-24 | Complete | 2026-03-24 |
| 4. Data Quality | 2/2 | Complete   | 2026-03-24 | Complete | 2026-03-24 |
| 5. State Data | 3/3 | Complete   | 2026-03-24 | Complete | 2026-03-24 |
| 6. Advanced API + Web UI | 2/2 | Complete   | 2026-03-24 | Complete | 2026-03-24 |
| 7. GTM + Enrichment | 2/2 | Complete   | 2026-03-24 | Complete | 2026-03-24 |
| 8. Pipeline & Data Cleanup | 2/2 | Complete   | 2026-03-24 | Not started | - |
| 9. API & Feature Polish | 2/2 | Complete   | 2026-03-24 | Not started | - |
| 11. ADA Compliance Grant Tagging & API | 0/2 | Phase 10 | Not started | Not started | - |
| 12. Fund Your Fix Web Page & SEO | 0/0 | Phase 11 | Not started | Not started | - |

### Phase 10: Data Population & Validation
**Goal**: Actually run all pipelines (SBIR, SAM.gov, state scrapers, LLM enrichment), fix what breaks, verify normalization produces human-readable labels, and validate the data makes the product useful
**Depends on**: Phase 9
**Wave**: 6 (data population)
**Requirements**: PIPE-03, PIPE-04, STATE-02, QUAL-01, QUAL-04
**Success Criteria** (what must be TRUE):
  1. SBIR ingestion completes successfully with >0 records in the database
  2. SAM.gov ingestion completes successfully with contract opportunities loaded
  3. State scrapers run for all configured states with data in the unified schema
  4. LLM enrichment populates topic_tags on a meaningful sample of opportunities
  5. Eligibility fields show human-readable labels (not raw codes like "25")
  6. Category fields show human-readable names (not raw codes like "D")
  7. The API returns multi-source data with normalized, useful field values
**Plans**: 4 plans

Plans:
- [ ] 10-01-PLAN.md — Add missing category/funding_instrument normalizers, wire into ingestors, backfill all 81K existing records
- [ ] 10-02-PLAN.md — Diagnose and fix SBIR crash, configure and run SAM.gov ingestion
- [ ] 10-03-PLAN.md — Build NC state scraper (with county-level grants), discover dataset IDs, run all state scrapers
- [ ] 10-04-PLAN.md — Run LLM enrichment, validate all data end-to-end across all sources
