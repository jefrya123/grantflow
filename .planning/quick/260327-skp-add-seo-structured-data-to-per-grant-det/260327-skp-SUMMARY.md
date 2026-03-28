---
phase: quick
plan: 260327-skp
subsystem: web-ui/seo
tags: [seo, structured-data, json-ld, open-graph, twitter-card, templates]
dependency_graph:
  requires: []
  provides: [detail-page-seo]
  affects: [templates/detail.html, tests/test_web_ui.py]
tech_stack:
  added: []
  patterns: [json-ld-schema-org, open-graph-meta, twitter-card-meta, jinja2-head-extra-block]
key_files:
  created: []
  modified:
    - templates/detail.html
    - tests/test_web_ui.py
key_decisions:
  - "JSON-LD uses GovernmentService @type (not Grant) — matches schema.org vocabulary for government-administered funding programs"
  - "Jinja2 |e filter on description fields in JSON-LD — prevents JSON breakage from quotes and special chars in grant descriptions"
  - "Comma placement in JSON-LD uses Jinja2 conditionals to produce valid JSON regardless of which optional fields are present"
metrics:
  duration: 8min
  completed: 2026-03-27
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 260327-skp: SEO Structured Data for Per-Grant Detail Pages Summary

**One-liner:** JSON-LD GovernmentService schema, Open Graph, and Twitter Card meta tags added to `/opportunity/{id}` detail pages via `{% block head_extra %}`.

## What Was Done

Added SEO structured data to the grant detail page template (`templates/detail.html`) following the existing pattern established in `templates/agency.html`.

### Changes

**templates/detail.html** — Added `{% block head_extra %}` block between `{% block title %}` and `{% block content %}` containing:
- `<meta name="description">` with 160-char truncated description
- Open Graph tags: `og:title`, `og:description`, `og:type`, `og:url` (using `request.url`)
- Twitter Card tags: `twitter:card`, `twitter:title`, `twitter:description`
- JSON-LD `<script type="application/ld+json">` with `GovernmentService` schema including optional `serviceOperator` (GovernmentOrganization) and `areaServed` fields

**tests/test_web_ui.py** — Added 4 tests under `WEB-05: Detail page SEO structured data`:
- `test_detail_seo_jsonld` — verifies `application/ld+json` and `GovernmentService` present
- `test_detail_seo_og_tags` — verifies `og:title`, `og:description`, `og:type` present
- `test_detail_seo_twitter_card` — verifies `twitter:card`, `twitter:title` present
- `test_detail_seo_includes_agency` — verifies agency renders as `GovernmentOrganization` serviceOperator

## Execution

TDD flow followed:
1. RED: wrote 4 failing tests, committed `7c8d1c1`
2. GREEN: implemented `{% block head_extra %}` in detail.html, all 4 tests pass, committed `3e56672`

## Test Results

- 4 new SEO tests: PASS
- Full suite (234 tests): PASS (1 xpassed)
- ruff: pre-existing E402/F841 violations in app.py and test_web_ui.py (out of scope — existed before this task)
- mypy: not installed in project (pre-existing)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all fields wired directly to `opp.*` ORM fields passed by the detail_page route.

## Self-Check

- [x] `templates/detail.html` contains `{% block head_extra %}` with JSON-LD, OG, and Twitter Card
- [x] `tests/test_web_ui.py` contains `test_detail_seo_jsonld`, `test_detail_seo_og_tags`, `test_detail_seo_twitter_card`, `test_detail_seo_includes_agency`
- [x] Commits `7c8d1c1` (test RED), `3e56672` (feat GREEN), `8c62ff8` (final) exist on main
- [x] Pushed to origin/main

## Self-Check: PASSED
