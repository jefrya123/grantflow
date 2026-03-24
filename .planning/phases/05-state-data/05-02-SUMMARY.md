---
phase: 05-state-data
plan: "02"
subsystem: ingest
tags: [state-scrapers, ckan, socrata, scrapling, httpx, california, new-york, illinois, texas, colorado]

requires:
  - phase: 05-state-data-01
    provides: BaseStateScraper abstract base class, SessionLocal, bind_source_logger, normalize_date/normalize_agency_name

provides:
  - CaliforniaScraper — CKAN API scraper for data.ca.gov with resource discovery and pagination
  - NewYorkScraper — Socrata API scraper for data.ny.gov with graceful env-var-gated skip
  - IllinoisScraper — CKAN API scraper for data.illinois.gov with graceful env-var-gated skip
  - TexasScraper — Socrata API scraper for data.texas.gov with graceful env-var-gated skip
  - ColoradoScraper — Scrapling Fetcher HTML scraper for Colorado grants portal

affects: [05-state-data-03, pipeline-scheduling, ingest-run-all]

tech-stack:
  added: [scrapling==0.4.2, curl-cffi==0.14.0, playwright==1.58.0, browserforge==1.2.4]
  patterns:
    - CKAN two-phase pattern: package_show resource discovery then datastore_search pagination
    - Socrata pagination: $limit/$offset loop until batch < page_size
    - Graceful env-var skip: unknown dataset IDs (NY, IL, TX) return [] with warning log, not error
    - Scrapling static HTML with auto_match=True and auto_save=True for resilient CSS selectors
    - HTML length logged alongside record count for breakage diagnosis

key-files:
  created:
    - grantflow/ingest/state/california.py
    - grantflow/ingest/state/new_york.py
    - grantflow/ingest/state/illinois.py
    - grantflow/ingest/state/texas.py
    - grantflow/ingest/state/colorado.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "CA uses hardcoded DATASET_ID='california-grants-portal' — public dataset, no env var needed"
  - "NY/IL/TX dataset IDs require PoC discovery — env-var gated with graceful empty-list skip"
  - "scrapling requires curl_cffi, playwright, browserforge as transitive deps — all added to pyproject.toml"
  - "Colorado source_id derived from title slug — no stable numeric IDs on HTML portal"
  - "Colorado scraper has CONDITIONAL legal status — ToS/robots.txt verification required before production"

patterns-established:
  - "State_{code}_{id} ID format via make_opportunity_id() for all 5 scrapers"
  - "CKAN pattern: package_show → resource discovery → datastore_search pagination"
  - "Socrata pattern: /resource/{id}.json?$limit=N&$offset=N until batch < page_size"
  - "HTML scraper: Scrapling Fetcher only (no Stealthy/DynamicFetcher) for government portals"

requirements-completed: [STATE-02]

duration: 2min
completed: 2026-03-24
---

# Phase 05 Plan 02: State Scrapers Implementation Summary

**Five state grant scrapers using CKAN API (CA, IL), Socrata API (NY, TX), and Scrapling HTML (CO) — completing the state data competitive moat**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T19:31:20Z
- **Completed:** 2026-03-24T19:33:48Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Implemented CaliforniaScraper with CKAN two-phase pattern: `package_show` resource discovery + paginated `datastore_search`
- Implemented NewYork, Illinois, and Texas scrapers (Socrata/CKAN) with graceful env-var-gated skip for dataset IDs not yet discovered
- Implemented ColoradoScraper using Scrapling Fetcher with `auto_match=True` and `auto_save=True` for resilient HTML extraction; handles table rows, list items, and article cards with fallback chain
- All 5 scrapers pass import verification, extend BaseStateScraper, and produce `state_{code}_{id}` format IDs

## Task Commits

1. **Task 1: CKAN and Socrata scrapers (CA, NY, IL, TX)** - `7717a8e` (feat)
2. **Task 2: Colorado HTML scraper + scrapling dependency** - `7e437a2` (feat)

## Files Created/Modified

- `grantflow/ingest/state/california.py` — CKAN API scraper: package_show resource discovery, paginated datastore_search
- `grantflow/ingest/state/new_york.py` — Socrata scraper: $limit/$offset pagination, GRANTFLOW_NY_DATASET_ID gated
- `grantflow/ingest/state/illinois.py` — CKAN scraper: same two-phase pattern, GRANTFLOW_IL_DATASET_ID gated
- `grantflow/ingest/state/texas.py` — Socrata scraper: $limit/$offset pagination, GRANTFLOW_TX_DATASET_ID gated
- `grantflow/ingest/state/colorado.py` — Scrapling Fetcher HTML scraper with fallback selector chain
- `pyproject.toml` — Added scrapling, curl-cffi, playwright, browserforge
- `uv.lock` — Updated lockfile

## Decisions Made

- California uses hardcoded `DATASET_ID = "california-grants-portal"` since it is a stable public dataset. NY, IL, TX require PoC dataset ID discovery so they use env-var gates with graceful empty-list returns.
- scrapling 0.4.2 pulls in `curl_cffi`, `playwright`, and `browserforge` as transitive requirements not auto-resolved by uv — added all to pyproject.toml explicitly.
- Colorado source_id is derived from a title slug (`re.sub` lowercased, max 80 chars) since the HTML portal has no stable numeric IDs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added missing scrapling transitive dependencies**
- **Found during:** Task 2 (Colorado scraper import verification)
- **Issue:** `scrapling` alone fails to import at module level — requires `curl_cffi`, `playwright`, and `browserforge` which are not auto-installed as transitive deps
- **Fix:** Ran `uv add curl_cffi playwright browserforge` to add all three
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** `uv run python -c "from grantflow.ingest.state.colorado import ColoradoScraper"` passes
- **Committed in:** `7e437a2` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required to unblock scraper import. No scope creep.

## Issues Encountered

- scrapling 0.4.2 on Python 3.13 requires explicit installation of `curl_cffi`, `playwright`, and `browserforge` — uv does not pull them automatically as optional deps. All resolved with `uv add`.

## User Setup Required

To enable scrapers for states with undiscovered dataset IDs, set environment variables:

```
GRANTFLOW_NY_DATASET_ID=<discovered-socrata-dataset-id>
GRANTFLOW_IL_DATASET_ID=<discovered-ckan-dataset-id>
GRANTFLOW_TX_DATASET_ID=<discovered-socrata-dataset-id>
GRANTFLOW_CO_PORTAL_URL=https://choosecolorado.com/doing-business/support-services/grants/  # already defaulted
```

Colorado scraper has CONDITIONAL legal status — verify ToS/robots.txt before production use (see LEGAL_REVIEW.md).

## Next Phase Readiness

- All 5 scraper classes are importable and implement the BaseStateScraper contract
- Plan 03 (scheduler wiring) can now import and invoke all 5 scrapers
- Dataset ID discovery PoC needed for NY, IL, TX before those scrapers produce data
- Scrapling v0.4 validated as importable on Python 3.13; actual portal fetch PoC pending

---
*Phase: 05-state-data*
*Completed: 2026-03-24*
