---
phase: 11
slug: ada-compliance-grant-tagging-api
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | none — pytest finds tests/ by convention |
| **Quick run command** | `uv run pytest tests/test_ada_compliance.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_ada_compliance.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | ADA-01 | unit | `uv run pytest tests/test_ada_compliance.py::test_keyword_matching -x` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | ADA-01 | unit | `uv run pytest tests/test_ada_compliance.py::test_backfill_tags_matching_records -x` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | ADA-01 | unit | `uv run pytest tests/test_ada_compliance.py::test_backfill_malformed_tags -x` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | ADA-01 | unit | `uv run pytest tests/test_ada_compliance.py::test_backfill_idempotent -x` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 1 | ADA-02 | integration | `uv run pytest tests/test_ada_compliance.py::test_endpoint_returns_200 -x` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 1 | ADA-02 | integration | `uv run pytest tests/test_ada_compliance.py::test_endpoint_response_fields -x` | ❌ W0 | ⬜ pending |
| 11-02-03 | 02 | 1 | ADA-02 | integration | `uv run pytest tests/test_ada_compliance.py::test_endpoint_sort_order -x` | ❌ W0 | ⬜ pending |
| 11-02-04 | 02 | 1 | ADA-02 | integration | `uv run pytest tests/test_ada_compliance.py::test_endpoint_pagination -x` | ❌ W0 | ⬜ pending |
| 11-02-05 | 02 | 1 | ADA-03 | integration | `uv run pytest tests/test_ada_compliance.py::test_municipality_filter -x` | ❌ W0 | ⬜ pending |
| 11-02-06 | 02 | 1 | ADA-03 | integration | `uv run pytest tests/test_ada_compliance.py::test_municipality_fallback -x` | ❌ W0 | ⬜ pending |
| 11-02-07 | 02 | 1 | ADA-03 | integration | `uv run pytest tests/test_ada_compliance.py::test_invalid_param_422 -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ada_compliance.py` — covers all ADA-01, ADA-02, ADA-03 requirements (does not exist yet)

*All test infrastructure (pytest) already installed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DOT FTA "All Stations Access" grant appears in live results | ADA-02 | Requires live DB with ingested data | Run `curl http://localhost:8000/api/v1/opportunities/ada-compliance` and verify "All Stations" in response |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
