---
phase: 12-fund-your-fix-web-page-seo
plan: "01"
subsystem: web
tags: [seo, fund-your-fix, municipality-filter, widget, redirect]
dependency_graph:
  requires: []
  provides: [fund-your-fix-municipality-filter, ada-grants-redirect, fund-your-fix-widget, og-image-meta]
  affects: [grantflow/web/routes.py, templates/fund_your_fix.html, templates/fund_your_fix_widget.html]
tech_stack:
  added: []
  patterns: [fail-open-municipality-filter, fta-featured-pinning, standalone-widget-template]
key_files:
  created:
    - templates/fund_your_fix_widget.html
  modified:
    - grantflow/web/routes.py
    - templates/fund_your_fix.html
decisions:
  - Municipality filter uses fail-open ilike pattern matching eligible_applicants and description — mirrors API route pattern from Phase 11
  - FTA grant pinned by title ilike "%all stations%" — specific enough to avoid false positives
  - /fund-your-fix/widget registered before /{opportunity_id} path-param route — FastAPI static-before-param ordering
  - Widget template is standalone HTML (no extends base.html) for iframe embedding
metrics:
  duration: 2
  completed_date: "2026-03-28"
  tasks_completed: 2
  files_changed: 3
---

# Phase 12 Plan 01: Fund Your Fix Web Page SEO Summary

Municipality filtering with fail-open fallback, DOT FTA featured grant pinning, /ada-grants 301 redirect, embeddable widget endpoint, og:image meta tag, and municipality banner added to the Fund Your Fix page.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add municipality filter, FTA pinning, /ada-grants redirect, widget endpoint | 1a2ccd3 | grantflow/web/routes.py |
| 2 | Add og:image and municipality banner to template, create widget template | f209d39 | templates/fund_your_fix.html, templates/fund_your_fix_widget.html |

## What Was Built

**Task 1 — routes.py:**
- Added `or_` and `RedirectResponse` imports
- Added `/ada-grants` GET route returning 301 redirect to `/fund-your-fix` (placed before the main route)
- Modified `fund_your_fix_page()` to accept `municipality: str | None = Query(default=None)` parameter
- Municipality filter applies ilike on `eligible_applicants` and `description` with fail-open fallback (if no results, return all ADA grants)
- FTA "All Stations Access" grant pinned as featured via separate query with `title.ilike("%all stations%")`, overriding soonest-deadline default
- `featured_is_fta` boolean added to template context
- Added `/fund-your-fix/widget` endpoint returning top 5 ADA grants in standalone HTML template

**Task 2 — templates:**
- Added `og:image` meta tag (`/static/og-fund-your-fix.png`) to `fund_your_fix.html` head_extra block
- Added municipality banner (blue info box with "Clear filter" link) between hero and featured grant
- Updated featured grant label to conditionally show "Featured: DOT FTA Grant" vs "Most Urgent Deadline"
- Updated pagination Previous/Next/numbered links to preserve `municipality` query param
- Created `templates/fund_your_fix_widget.html` as standalone HTML fragment (no base.html extends) with minimal CSS, top-5 grant items, and link back to full page

## Verification

- All 3 routes importable: `/ada-grants`, `/fund-your-fix`, `/fund-your-fix/widget`
- Template checks: og:image present, municipality banner present, featured_is_fta conditional present, widget has no base.html reference
- `uv run pytest tests/test_fund_your_fix.py`: 5/5 passed
- `uv run ruff check . --fix && uv run ruff format .`: All checks passed, 79 files unchanged

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `/home/jeff/Projects/grantflow/.claude/worktrees/agent-ab2630ea/grantflow/web/routes.py` — exists with all required functions
- `/home/jeff/Projects/grantflow/.claude/worktrees/agent-ab2630ea/templates/fund_your_fix.html` — exists with og:image and municipality banner
- `/home/jeff/Projects/grantflow/.claude/worktrees/agent-ab2630ea/templates/fund_your_fix_widget.html` — exists as standalone HTML fragment
- Commits 1a2ccd3 and f209d39 present in git log
