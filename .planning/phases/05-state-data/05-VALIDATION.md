---
phase: 5
slug: state-data
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_state_scrapers.py tests/test_state_monitor.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_state_scrapers.py tests/test_state_monitor.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | STATE-01 | unit | `uv run pytest tests/test_state_scrapers.py::test_base_scraper_stats_shape -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 0 | STATE-01 | unit | `uv run pytest tests/test_state_scrapers.py::test_normalize_ca_record -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 0 | STATE-01 | unit | `uv run pytest tests/test_state_scrapers.py::test_opportunity_id_prefix -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | STATE-02 | integration | Manual: query DB after first full run | N/A | ⬜ pending |
| 05-03-01 | 03 | 1 | STATE-03 | manual-only | N/A — LEGAL_REVIEW.md | N/A | ⬜ pending |
| 05-04-01 | 04 | 1 | STATE-04 | unit | `uv run pytest tests/test_state_monitor.py::test_zero_records_detection -x` | ❌ W0 | ⬜ pending |
| 05-04-02 | 04 | 1 | STATE-04 | unit | `uv run pytest tests/test_state_monitor.py::test_state_stale_threshold -x` | ❌ W0 | ⬜ pending |
| 05-05-01 | 05 | 1 | STATE-05 | unit | `uv run pytest tests/test_state_scrapers.py::test_scheduler_weekly_job -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_state_scrapers.py` — stubs for STATE-01 (stats shape, normalization, ID prefix) and STATE-05 (scheduler job)
- [ ] `tests/test_state_monitor.py` — stubs for STATE-04 (zero-records detection, per-source stale threshold)

*Existing test infrastructure (conftest.py, pytest config) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Legal review checklist per portal | STATE-03 | Legal/policy judgement, not automatable | Review ToS/robots.txt for each portal, document findings in LEGAL_REVIEW.md |
| 5+ state sources in DB | STATE-02 | Requires live data from all portals | Query `SELECT DISTINCT source FROM opportunities WHERE source LIKE 'state_%'` after full run |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
