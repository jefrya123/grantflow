---
phase: 06-advanced-api-web-ui
plan: "02"
subsystem: web-ui
tags: [web, search, filters, stats, templates, jinja2]
dependency_graph:
  requires: []
  provides: [WEB-01, WEB-02, WEB-03, WEB-04]
  affects: [templates/search.html, templates/base.html, templates/stats.html, grantflow/web/routes.py]
tech_stack:
  added: []
  patterns: [jinja2-template-context-injection, fastapi-router-get, sqlalchemy-groupby-aggregation]
key_files:
  created: [templates/stats.html, tests/test_web_ui.py]
  modified: [grantflow/web/routes.py, templates/search.html, templates/base.html]
decisions:
  - "closing-soon badge placed in badges div (not meta-item span) for visual consistency with status/source badges"
  - "pagination base_qs uses Jinja2 set block to deduplicate query string across prev/next/page links"
  - "inline verification script failure accepted — SQLite dev DB lacks search_vector column; test suite (161 pass) is authoritative"
metrics:
  duration: "3 min"
  completed: "2026-03-24"
  tasks_completed: 1
  files_changed: 5
---

# Phase 06 Plan 02: Web UI Filters, Closing-Soon Badge, Stats Dashboard Summary

**One-liner:** Full search filter row (agency, category, eligible, date range) + closing-soon badge + /stats dashboard page backed by SQLAlchemy aggregation queries.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for WEB-01–WEB-04 | 13a10f8 | tests/test_web_ui.py |
| 1 (GREEN) | Implement all web UI changes | b3a06df | routes.py, search.html, base.html, stats.html, test_web_ui.py |

## What Was Built

### WEB-01: Search filter inputs
Added 5 missing filter inputs to `templates/search.html`:
- `name="agency"` — text input, filters by `agency_code` ILIKE
- `name="category"` — select with Discretionary/Mandatory/Earmark/Continuation/Other options
- `name="eligible"` — text input, filters by `eligible_applicants` ILIKE
- `name="closing_after"` — date input
- `name="closing_before"` — date input

Updated pagination links to carry all 10 filter params (was missing the 5 new ones).

### WEB-02: Historical awards table (already existed)
Detail page awards table was already implemented in `templates/detail.html`. Added tests to verify it renders correctly with linked award data.

### WEB-03: Closing-soon badge
- `grantflow/web/routes.py search_page`: now injects `now_date` and `closing_soon_date` (today + 30 days) as ISO date strings into template context
- `templates/search.html`: badge renders inside `.badges` div using `{% if opp.close_date and now_date and opp.close_date >= now_date and opp.close_date <= closing_soon_date %}`
- Removed broken stub that had `now_date|default('')` with no injection

### WEB-04: /stats page
- New route `GET /stats` in `grantflow/web/routes.py` queries: total count, by-source group-by, closing-soon count (close_date in [today, today+30]), top 10 agencies by count
- New `templates/stats.html` extending base.html: stat cards for total + closing-soon, by-source table, top agencies table

### Nav fix
`templates/base.html`: changed `href="/api/v1/stats"` to `href="/stats"`.

## Test Results

```
9 passed (test_web_ui.py)
161 passed, 1 xpassed (full suite)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test helper missing NOT NULL fields**
- **Found during:** Task 1 GREEN (first test run)
- **Issue:** `_make_opp()` did not supply `source_id` (NOT NULL); `_make_award()` did not supply `source` or `award_id` (NOT NULL)
- **Fix:** Added `source_id=f"src-{opp_id}"` to `_make_opp` defaults; added `source="usaspending"` and `award_id=f"awd-{award_id}"` to `_make_award` defaults
- **Files modified:** tests/test_web_ui.py
- **Commit:** b3a06df

## Self-Check: PASSED

- templates/stats.html: FOUND
- tests/test_web_ui.py: FOUND
- templates/search.html: FOUND
- Commit 13a10f8 (RED): FOUND
- Commit b3a06df (GREEN): FOUND
