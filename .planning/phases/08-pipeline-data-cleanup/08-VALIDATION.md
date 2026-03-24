---
phase: 8
slug: pipeline-data-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_sam_gov.py tests/test_normalizers.py tests/test_pipeline_cleanup.py -x` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_sam_gov.py tests/test_normalizers.py tests/test_pipeline_cleanup.py -x`
- **After every plan wave:** Run `uv run pytest -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | FOUND-02 | smoke | `uv run pytest tests/test_pipeline_cleanup.py::test_no_fts5_references -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | QUAL-06 | smoke | `uv run pytest tests/test_pipeline_cleanup.py::test_sbir_no_dead_import -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | QUAL-01 | unit | `uv run pytest tests/test_sam_gov.py::test_sam_gov_normalizes_eligibility -x` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 1 | QUAL-02 | unit | `uv run pytest tests/test_sam_gov.py::test_sam_gov_normalizes_agency -x` | ❌ W0 | ⬜ pending |
| 08-01-05 | 01 | 1 | QUAL-05 | unit | `uv run pytest tests/test_sam_gov.py -x` | ✅ (update) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline_cleanup.py` — smoke tests for FOUND-02 (no FTS5) and QUAL-06 (no dead import)
- [ ] Update `tests/test_sam_gov.py` — migrate _parse_sam_date tests to normalize_date, add normalization wire tests

*Existing test infrastructure covers all other needs.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
