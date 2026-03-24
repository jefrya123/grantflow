---
phase: 6
slug: advanced-api-web-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_export.py tests/test_agencies.py tests/test_web_ui.py -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_export.py tests/test_agencies.py tests/test_web_ui.py -x -q`
- **After every plan wave:** Run `uv run pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | API-05 | integration | `uv run pytest tests/test_export.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 0 | API-05 | integration | `uv run pytest tests/test_export.py::test_export_json -x` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 0 | API-05 | unit | `uv run pytest tests/test_export.py::test_export_no_key -x` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 0 | API-05 | integration | `uv run pytest tests/test_export.py::test_export_filters -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | API-06 | integration | `uv run pytest tests/test_schemas.py::test_opportunity_detail_awards -x` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | API-08 | integration | `uv run pytest tests/test_agencies.py -x -q` | ❌ W0 | ⬜ pending |
| 06-02-03 | 02 | 1 | API-08 | unit | `uv run pytest tests/test_agencies.py::test_agency_schema -x` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 1 | WEB-01 | unit | `uv run pytest tests/test_web_ui.py::test_search_filter_inputs -x` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 1 | WEB-02 | integration | `uv run pytest tests/test_web_ui.py::test_detail_awards_section -x` | ❌ W0 | ⬜ pending |
| 06-03-03 | 03 | 1 | WEB-03 | unit | `uv run pytest tests/test_web_ui.py::test_closing_soon_badge -x` | ❌ W0 | ⬜ pending |
| 06-03-04 | 03 | 1 | WEB-04 | integration | `uv run pytest tests/test_web_ui.py::test_stats_page -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_export.py` — covers API-05 (bulk export CSV + JSON + auth + filters)
- [ ] `tests/test_agencies.py` — covers API-08 (agencies endpoint + Pydantic schema)
- [ ] `tests/test_web_ui.py` — covers WEB-01, WEB-02, WEB-03, WEB-04 (rendered HTML checks via TestClient)
- [ ] Extend `tests/test_schemas.py` for API-06 detail+awards

*Existing test infrastructure (conftest.py, pytest config) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual layout of search filters | WEB-01 | CSS/layout correctness not automatable via TestClient | Open /search in browser, verify filter panel renders correctly |
| Closing-soon badge visual styling | WEB-03 | CSS class presence testable, visual rendering is not | Open search results with near-deadline opps, verify badge visibility |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
