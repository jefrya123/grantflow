# Requirements: GrantFlow

**Defined:** 2026-03-24
**Core Value:** Make government grant data discoverable, clean, and instantly accessible

## v1 Requirements

### Foundation

- [x] **FOUND-01**: Database migrated from SQLite to PostgreSQL with Alembic migrations
- [x] **FOUND-02**: Full-text search uses PostgreSQL tsvector + GIN index (replacing FTS5)
- [x] **FOUND-03**: Environment config supports production PostgreSQL connection
- [x] **FOUND-04**: Health endpoint returns pipeline freshness and record counts

### Pipeline

- [x] **PIPE-01**: Grants.gov ingestion runs automatically on daily schedule
- [x] **PIPE-02**: USAspending ingestion runs automatically with incremental updates
- [x] **PIPE-03**: SBIR ingestion works reliably (fix rate limiting, retry logic)
- [x] **PIPE-04**: SAM.gov contract opportunities ingested (with registered API key, incremental design)
- [x] **PIPE-05**: Pipeline monitoring detects stale data (no update in 48h triggers alert)
- [x] **PIPE-06**: Pipeline logs ingestion stats (records added/updated/failed per run)
- [x] **PIPE-07**: Cross-source joining links opportunities to historical awards via CFDA/ALN numbers
- [x] **PIPE-08**: Grants.gov ingestion supports both XML extract and new REST API (migration-safe)


### Data Quality

- [x] **QUAL-01**: Eligibility codes normalized to human-readable categories
- [x] **QUAL-02**: Agency names/codes normalized across all sources
- [x] **QUAL-03**: Duplicate opportunities detected and merged across sources
- [ ] **QUAL-04**: LLM-powered categorization tags opportunities by topic/sector
- [x] **QUAL-05**: Date fields consistently ISO 8601 across all sources
- [x] **QUAL-06**: Award amounts validated (floor <= ceiling, no negative values)

### State Data

- [x] **STATE-01**: Scraping infrastructure for state grant portals using Scrapling
- [x] **STATE-02**: At least 5 state portals scraped and normalized into unified schema
- [x] **STATE-03**: Per-state legal review completed (ToS/robots.txt/open-data check)
- [x] **STATE-04**: Per-source monitoring alerts when a scraper breaks
- [x] **STATE-05**: State data refreshed on regular schedule (weekly minimum)

### API

- [x] **API-01**: API keys generated via self-serve endpoint (hash stored, plaintext shown once)
- [x] **API-02**: Rate limiting per API key with configurable tiers (free/starter/growth)
- [x] **API-03**: API versioned at /api/v1/ with stable schema contract
- [x] **API-04**: Consistent error responses with error codes and messages
- [x] **API-05**: Bulk export endpoint (CSV/JSON for search results)
- [x] **API-06**: Historical awards linked in opportunity detail responses
- [x] **API-07**: OpenAPI docs auto-generated and accurate
- [x] **API-08**: Agencies endpoint with opportunity counts

### Web UI

- [x] **WEB-01**: Search page with filters (status, agency, category, eligibility, dates, award range)
- [x] **WEB-02**: Opportunity detail page with linked awards
- [x] **WEB-03**: "Closing soon" badge on opportunities closing within 30 days
- [x] **WEB-04**: Stats dashboard (total opps, by source, by agency, closing soon)

### Go-to-Market

- [ ] **GTM-01**: Landing page explaining product value proposition
- [ ] **GTM-02**: Pricing page with coverage-based tiers (not API call volume)
- [ ] **GTM-03**: Interactive API playground (try-it-now with sample data)
- [ ] **GTM-04**: Usage analytics tracking (endpoint hits, search queries, API key usage)

## v2 Requirements

### Enrichment

- **ENRICH-01**: Eligibility matching ("show grants I qualify for" based on org profile)
- **ENRICH-02**: Grant success rate predictions from historical award data
- **ENRICH-03**: Email digest alerts (closing soon, new in your category)

### Data Expansion

- **EXPAND-01**: Foundation grants from IRS 990 data
- **EXPAND-02**: Coverage expanded to 25+ states
- **EXPAND-03**: Local/municipal grant programs (top 50 cities)

### Platform

- **PLAT-01**: User accounts with saved searches and watchlists
- **PLAT-02**: Stripe billing integration
- **PLAT-03**: Webhook notifications for new opportunities matching criteria

## Out of Scope

| Feature | Reason |
|---------|--------|
| Grant application writing/AI | Instrumentl's territory ($55M raised). We're data infrastructure, not workflow. |
| User accounts for v1 | Validate demand with API keys before building auth complexity |
| Stripe/billing for v1 | Learned from AgentGrade — validate demand first, monetize later |
| Mobile app | Web-first, mobile adds no value for API product |
| Real-time data | Daily refresh sufficient for grants (deadlines are days/weeks away) |
| Social features | Not a community product |

## Traceability

| Requirement | Phase | Wave | Status |
|-------------|-------|------|--------|
| FOUND-01 | Phase 1: Foundation | 1 | Pending |
| FOUND-02 | Phase 1: Foundation | 1 | Pending |
| FOUND-03 | Phase 1: Foundation | 1 | Pending |
| FOUND-04 | Phase 1: Foundation | 1 | Pending |
| PIPE-01 | Phase 2: Pipeline Hardening | 2 | Pending |
| PIPE-02 | Phase 2: Pipeline Hardening | 2 | Pending |
| PIPE-03 | Phase 2: Pipeline Hardening | 2 | Pending |
| PIPE-04 | Phase 2: Pipeline Hardening | 2 | Pending |
| PIPE-05 | Phase 2: Pipeline Hardening | 2 | Pending |
| PIPE-06 | Phase 2: Pipeline Hardening | 2 | Pending |
| PIPE-07 | Phase 2: Pipeline Hardening | 2 | Pending |
| PIPE-08 | Phase 2: Pipeline Hardening | 2 | Pending |

| QUAL-01 | Phase 4: Data Quality | 2 | Pending |
| QUAL-02 | Phase 4: Data Quality | 2 | Pending |
| QUAL-03 | Phase 4: Data Quality | 2 | Pending |
| QUAL-04 | Phase 7: GTM + Enrichment | 4 | Pending |
| QUAL-05 | Phase 4: Data Quality | 2 | Pending |
| QUAL-06 | Phase 4: Data Quality | 2 | Pending |
| STATE-01 | Phase 5: State Data | 3 | Pending |
| STATE-02 | Phase 5: State Data | 3 | Pending |
| STATE-03 | Phase 5: State Data | 3 | Pending |
| STATE-04 | Phase 5: State Data | 3 | Pending |
| STATE-05 | Phase 5: State Data | 3 | Pending |
| API-01 | Phase 3: API Key Infrastructure | 2 | Pending |
| API-02 | Phase 3: API Key Infrastructure | 2 | Pending |
| API-03 | Phase 3: API Key Infrastructure | 2 | Pending |
| API-04 | Phase 3: API Key Infrastructure | 2 | Pending |
| API-05 | Phase 6: Advanced API + Web UI | 3 | Pending |
| API-06 | Phase 6: Advanced API + Web UI | 3 | Pending |
| API-07 | Phase 3: API Key Infrastructure | 2 | Pending |
| API-08 | Phase 6: Advanced API + Web UI | 3 | Pending |
| WEB-01 | Phase 6: Advanced API + Web UI | 3 | Pending |
| WEB-02 | Phase 6: Advanced API + Web UI | 3 | Pending |
| WEB-03 | Phase 6: Advanced API + Web UI | 3 | Pending |
| WEB-04 | Phase 6: Advanced API + Web UI | 3 | Pending |
| GTM-01 | Phase 7: GTM + Enrichment | 4 | Pending |
| GTM-02 | Phase 7: GTM + Enrichment | 4 | Pending |
| GTM-03 | Phase 7: GTM + Enrichment | 4 | Pending |
| GTM-04 | Phase 7: GTM + Enrichment | 4 | Pending |

**Coverage:**
- v1 requirements: 35 total
- Mapped to phases: 36
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 — restructured to 7-phase wave model*
