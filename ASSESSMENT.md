# GrantFlow Project Assessment

**Date:** 2026-03-27
**Assessor:** PM Review
**Recommendation:** INVEST

---

## 1. Executive Summary

GrantFlow is a government grants data API and search platform built on FastAPI + SQLAlchemy, aggregating federal and state grant opportunities from sources including Grants.gov, USASpending, SBIR, and six state portals. The database currently holds 98,948 grant opportunities and 11,276 historical awards, served through a tiered REST API with full-text search, bulk export, and an interactive web UI.

The product is further along than it appears at first glance. The test suite has 218 passing tests, the API key tier system is built and ready for monetization, and there is already one power user generating 990 analytics events — including 164 bulk exports — using a single demo key. That user is a conversion opportunity waiting to happen.

The critical issues are fixable: a broken Colorado scraper, SBIR records that aren't surfacing in the opportunities table, an untracked Alembic migration, and a scheduling architecture that depends on the FastAPI process staying up. None of these are architectural rewrites — they are Medium-effort patches. Combined with a unique "Fund Your Fix" integration path via ada-audit for ADA compliance grants, GrantFlow has a defensible competitive position that generic grant aggregators cannot easily replicate.

---

## 2. What Works

| Feature | Status |
|---|---|
| Test suite | 218 passing tests |
| Core data | 98,948 opportunities + 11,276 awards in DB |
| Full-text search | FTS5 (SQLite dev) / tsvector GIN index (PostgreSQL prod) |
| REST API | 7 endpoints with 3-tier key system (free/starter/growth) + rate limiting |
| Web UI | Search, detail pages, stats dashboard, pricing page, API playground |
| Data ingestion | Grants.gov + USASpending + 5 working state scrapers + SBIR pipeline |
| Analytics | `api_events` table logs all API calls non-blocking via middleware |
| Real usage | 1 power user: 164 exports, 136 searches, 190 key-create calls |

The architecture choices are solid. FastAPI + SQLAlchemy is a well-understood, production-proven stack. The FTS5/tsvector dual-mode search is clever — it means local development works without PostgreSQL while production can use the more powerful tsvector. The 3-tier API key system with per-tier rate limiting via `slowapi` means monetization infrastructure exists and only needs a payment integration, not a redesign.

---

## 3. What's Broken or Missing

| Issue | Severity | Notes |
|---|---|---|
| Colorado scraper | High | 1 record ingested — effectively dead |
| SBIR data missing from opportunities | High | 6,276 records ingested to success, zero appear in `opportunities` table (likely going to `awards` or being dropped) |
| SAM.gov scraper | Medium | `sam_gov.py` exists, no `pipeline_runs` or `ingestion_log` entries — never ran |
| Alembic version drift | Low | DB at `0006`, migration `0007` (api_events table) applied outside Alembic; one command to fix |
| APScheduler fragility | Medium | Ingestion jobs only run while FastAPI process is up; server restart at 02:00 UTC = missed ingest |
| No external cron/worker | Medium | No Celery, no OS cron, no systemd timer backing up the scheduler |
| Stale data | High | All 98,948 opportunities loaded 2026-03-24 in a single batch; no evidence of recurring ingestion running since |

The data staleness issue deserves emphasis: the `created_at` column on all opportunities is `2026-03-24`. The APScheduler is configured to run daily, but since there's no external process management confirmed, it's unclear whether ingestion has actually run since the initial load. This is the highest-priority operational risk.

---

## 4. Data Coverage

| Source | Records | Type | Last Ingest | Notes |
|---|---|---|---|---|
| grants_gov | 81,856 | Opportunities | 2026-03-24 | Federal; dominant source |
| state_illinois | 9,316 | Opportunities | 2026-03-24 | Playwright scraper |
| state_new_york | 2,738 | Opportunities | 2026-03-24 | Playwright scraper |
| state_california | 1,869 | Opportunities | 2026-03-24 | Playwright scraper |
| state_texas | 1,730 | Opportunities | 2026-03-24 | Playwright scraper |
| state_north_carolina | 1,438 | Opportunities | 2026-03-24 | Playwright scraper |
| state_colorado | 1 | Opportunities | 2026-03-24 | Scraper broken |
| usaspending | 11,276 | Awards | 2026-03-24 | Historical awards |
| sbir | 6,276 | Unknown | 2026-03-24 | Not surfacing in opportunities |
| sam_gov | 0 | — | Never | Scraper exists, never ran |

**Opportunity post_date range:** 2004-03-22 → 2026-06-20
**Awards date range:** 1975-06-28 → 2026-07-01

The 44-state gap in state coverage is a known growth opportunity. The 5 working state scrapers demonstrate the pattern is proven — the marginal cost of adding each new state is low once the template exists.

---

## 5. Architecture Assessment

### Strengths

- **FastAPI + SQLAlchemy** is the right foundation. It's well-documented, easy to deploy, and the ORM makes the PostgreSQL migration straightforward.
- **FTS5 dev / tsvector prod** is pragmatic. Developers can run locally without PostgreSQL overhead, and the production path to proper GIN-indexed full-text search is already wired in.
- **3-tier API key system** is ready for monetization. The tiers (free/starter/growth) with per-tier rate limiting are implemented. Adding Stripe checkout is the only missing piece.
- **Analytics middleware** is non-blocking and already capturing usage data. The `api_events` table is the foundation of a usage dashboard and conversion funnel analysis.
- **Alembic migrations** provide a clean upgrade path, despite the current drift.

### Gaps

- **SQLite in production** will hit write-lock contention under any meaningful concurrent load. FTS5 also lacks the query planning sophistication of tsvector. PostgreSQL migration is required before any serious traffic.
- **APScheduler-only scheduling** is fragile. If the FastAPI process dies and is restarted by a process manager, APScheduler reinitializes but doesn't fire missed jobs beyond the 1-hour grace window. Under any deployment scenario with restarts (deploys, crashes, scaling), ingestion will silently fail.
- **No health monitoring beyond `/health`** — the endpoint reports pipeline freshness but nothing alerts externally if ingestion stops running. This is how the data goes stale undetected.
- **No authentication on web UI** — acceptable for public search, but bulk export is API-key-gated only. Pricing page suggests intent to convert visitors; a registration flow is missing.

---

## 6. Revenue Potential

### Immediate Opportunities

**Convert the power user.** One account holds the only API key in the database and has made 164 export calls and 136 search calls. This is bulk programmatic usage — not casual browsing. The `api_keys` table has a `key_prefix` column; identifying this user and making a direct outreach with a paid plan offer (Growth tier at ~$99–199/mo) is the fastest path to first revenue. This user is already getting value; the conversion friction is minimal.

**"Fund Your Fix" — ada-audit integration.** GrantFlow + ada-audit serve the same government buyer (city IT director + grant writer). A curated "ADA Compliance" grant collection — surfacing grants like DOT FTA "All Stations Access" (closes 2026-05-01) for municipalities with documented ada-audit violations — creates precision grant matching that no generic aggregator can replicate. This is the primary competitive moat.

**Government Compliance Suite bundling.** Once both products have live web UIs, a bundled pitch to city procurement closes two sales in one conversation. The same buyer pain (ADA compliance + funding) becomes a single product.

### Competitive Landscape

| Competitor | Price | Weakness |
|---|---|---|
| Grants.gov | Free | Poor UX, no API, no state grants |
| GrantWatch | $199/yr | Expensive for individuals, no API |
| Foundation Directory (Candid) | $179+/mo | Focused on nonprofit/foundation grants |
| GrantFlow | TBD | Machine-readable API + state coverage + ada-audit integration |

The API-first approach and ada-audit integration create a niche that isn't currently served. Government grant writers need machine-readable data to build internal tools — Grants.gov doesn't offer this.

---

## 7. Effort Estimate to Production-Ready

| Task | Effort | Notes |
|---|---|---|
| Fix Colorado scraper | Low | Debug silent failure; likely a DOM change |
| Fix SBIR data pipeline | Medium | Trace where 6,276 records are going; likely a source field mismatch |
| Stamp Alembic to 0007 | Low | One command: `uv run alembic stamp 0007` |
| Add external cron or Celery for scheduling | Medium | OS cron calling `uv run python -m grantflow.ingest.run_all` is the simple path; Celery adds complexity but improves observability |
| PostgreSQL migration for production | Medium | ORM is already written for both; needs connection string + migration run + FTS index creation |
| SAM.gov integration | Medium-High | Code exists; may require API key registration + testing against live API |
| Monitoring and alerting | Low-Medium | Add staleness alert to `/health` + external ping (UptimeRobot/Better Stack); Sentry for exceptions |
| Payment integration (Stripe) | Medium | API key tiers are built; needs Stripe checkout + webhook to provision Growth keys |
| Power user conversion outreach | Low | Check `api_keys` table for contact info; draft one email |

Total to "production-ready with first paying customer": approximately 3–4 focused weeks of engineering time.

---

## 8. Recommendation

**INVEST.**

GrantFlow is a working product with real data, real users, and a monetization path that is 80% built. The issues catalogued above are operational and fixable — none require architectural rethinking.

**Priority order:**

1. **Fix data pipeline reliability** — stamp Alembic, add external cron, verify ingestion is actually running. Stale data kills trust.
2. **Fix SBIR + Colorado** — 6,277 records currently invisible or missing is a data quality gap that matters to users.
3. **Convert the power user** — look up `key_prefix` in `api_keys`, identify the user, send a paid plan offer. One conversion validates the business model.
4. **Build the Fund Your Fix integration** — curate ADA compliance grants, cross-link with ada-audit violations. This is the moat.
5. **PostgreSQL + monitoring** — required before any public launch or marketing spend.

The ada-audit integration is the insight that separates GrantFlow from every other grant aggregator. Generic grant search is a commodity. "Here are the grants that will fund fixing the accessibility violations we just found in your city's website" is a product. That's worth building.
