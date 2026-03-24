---
phase: 07-gtm-enrichment
plan: 01
subsystem: ui
tags: [fastapi, jinja2, sqlalchemy, analytics, middleware, alembic, background-tasks]

# Dependency graph
requires:
  - phase: 07-gtm-enrichment
    provides: "plan 02 — topic_tags column (migration 0006), needed for down_revision chain"
  - phase: 03-api-key-infrastructure
    provides: "ApiKey model and key creation pattern (gf_ prefix + SHA-256 hash)"
provides:
  - Landing page at GET / with value props, dynamic opp count, and CTAs to pricing/playground
  - Pricing page at GET /pricing with Free/Starter/Growth coverage-based tiers
  - Interactive API playground at GET /playground with vanilla JS fetch and demo key injection
  - ApiEvent ORM model and api_events table (migration 0007, down_revision=0006)
  - Non-blocking analytics middleware capturing every API request as BackgroundTask
  - scripts/seed_demo_key.py — idempotent demo API key provisioner
affects:
  - future analytics/reporting phases that read api_events
  - any phase that adds or changes routes (analytics fires on all non-static routes)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BackgroundTask analytics: attach record_api_event as response.background to avoid blocking response"
    - "Analytics middleware via @app.middleware('http') decorator (NOT BaseHTTPMiddleware)"
    - "Demo key pattern: gf_demo_p prefix for playground keys, identified by key_prefix"

key-files:
  created:
    - grantflow/analytics/__init__.py
    - grantflow/analytics/middleware.py
    - alembic/versions/0007_add_api_events.py
    - templates/landing.html
    - templates/pricing.html
    - templates/playground.html
    - scripts/seed_demo_key.py
    - tests/test_analytics.py
    - tests/test_gtm_pages.py
  modified:
    - grantflow/models.py
    - grantflow/app.py
    - grantflow/web/routes.py

key-decisions:
  - "Analytics middleware uses SessionLocal() directly in BackgroundTask (not get_db Depends) — avoids FastAPI dependency injection complexity in background context"
  - "Test for analytics writes to production SessionLocal (grantflow.db), not the test session — analytics is verified against the same DB the middleware writes to"
  - "Playground template renders gracefully when GRANTFLOW_DEMO_API_KEY is unset — no 500, shows message pointing to /docs"
  - "Pricing page is display-only with no Stripe integration — per project decision to skip billing until demand validated"
  - "GET / replaced with landing page (not redirect) — landing page now serves as the product homepage"

patterns-established:
  - "BackgroundTask analytics pattern: attach after call_next, chain with existing response.background"
  - "Static path guard in middleware: skip /static/ prefix to avoid recording asset fetches"

requirements-completed: [GTM-01, GTM-02, GTM-03, GTM-04]

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 7 Plan 1: GTM Pages and Analytics Middleware Summary

**Landing/pricing/playground pages with non-blocking BackgroundTask analytics capturing every API request to api_events table via Alembic migration 0007**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-24T16:28:01Z
- **Completed:** 2026-03-24T16:31:36Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Public product face: landing page replaces the / redirect, pricing shows coverage-based tiers, playground enables no-auth API exploration
- Non-blocking analytics: every API request creates an api_events row via BackgroundTask (response is sent before DB write)
- Full TDD: failing tests written first for both tasks, then implementation to pass
- Zero regressions: all 181 existing tests continue to pass

## Task Commits

1. **Task 1: Analytics DB model, middleware, and app wiring** - `a5d9d76` (feat)
2. **Task 2: GTM web pages, demo key seed, and page tests** - `0eaf809` (feat)

## Files Created/Modified

- `grantflow/models.py` — Added ApiEvent model (id, ts, path, method, api_key_prefix, query_string, status_code, duration_ms)
- `grantflow/analytics/__init__.py` — Empty package init
- `grantflow/analytics/middleware.py` — record_api_event() and setup_analytics_middleware() with BackgroundTask pattern
- `grantflow/app.py` — Wired setup_analytics_middleware(app) after CORS setup
- `alembic/versions/0007_add_api_events.py` — CREATE TABLE api_events, indexes on ts and api_key_prefix, down_revision='0006'
- `grantflow/web/routes.py` — Replaced GET / redirect with landing route; added GET /pricing and GET /playground
- `templates/landing.html` — Hero section, value props grid, dynamic opp count, CTA buttons
- `templates/pricing.html` — Three-tier pricing table (Free/Starter/Growth), coverage-based, display-only
- `templates/playground.html` — Vanilla JS fetch with demo key injection; graceful fallback when key absent
- `scripts/seed_demo_key.py` — Idempotent demo key provisioner (gf_demo_p prefix, SHA-256 stored)
- `tests/test_analytics.py` — test_event_recorded, test_analytics_skips_static
- `tests/test_gtm_pages.py` — test_landing_page, test_pricing_page, test_playground_page

## Decisions Made

- Analytics middleware uses its own `SessionLocal()` in the BackgroundTask rather than the route's DB session — background tasks run after the request lifecycle ends, so FastAPI's `Depends(get_db)` session is already closed.
- Test for analytics uses `SessionLocal()` directly (writes to `grantflow.db`) rather than the test session — verifies the actual middleware write path.
- Pricing page is display-only (no Stripe buttons) per the project decision from Phase 1 to skip billing until demand is validated.
- GET / now renders the landing page instead of redirecting — the product needed a public-facing homepage.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- First test implementation used the `db_session` fixture (test DB) to verify analytics events, but the middleware writes via its own `SessionLocal()` to the production/default DB. Fixed by updating the test to use `SessionLocal()` directly — the correct verification of the actual write path.

## User Setup Required

To enable the live playground, run the demo key seed script after deployment:

```bash
uv run python scripts/seed_demo_key.py
export GRANTFLOW_DEMO_API_KEY="<printed plaintext key>"
```

The playground falls back gracefully to a "Demo key not configured" message if this env var is unset.

## Next Phase Readiness

- GTM surface is complete: landing, pricing, playground all live
- api_events table is populated on every request — ready for analytics dashboards or usage-based billing in a future phase
- Migration chain is complete through 0007; any new migrations use down_revision='0007'
- Run `uv run alembic upgrade head` to apply migrations 0006 + 0007 in sequence on production

---
*Phase: 07-gtm-enrichment*
*Completed: 2026-03-24*

## Self-Check: PASSED

All 10 expected files found on disk. Both task commits (a5d9d76, 0eaf809) verified in git log.
