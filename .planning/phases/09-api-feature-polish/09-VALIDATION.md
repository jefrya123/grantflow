---
phase: 9
slug: api-feature-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_auth_ratelimit.py tests/test_export.py tests/test_schemas.py tests/test_enrichment.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_auth_ratelimit.py tests/test_export.py tests/test_schemas.py tests/test_enrichment.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | API-02 | unit | `uv run pytest tests/test_auth_ratelimit.py -x -q` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | API-05 | integration | `uv run pytest tests/test_export.py::test_export_topic_filter -x` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 1 | QUAL-03 | unit | `uv run pytest tests/test_schemas.py::test_opportunity_response_preserves_exact_field_names -x` | ✅ (update) | ⬜ pending |
| 09-01-04 | 01 | 1 | QUAL-04 | unit | `uv run pytest tests/test_enrichment.py::test_enrichment_scheduler_job_registered -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth_ratelimit.py` — tier limit callable tests (API-02)
- [ ] `tests/test_export.py` — topic filter tests (API-05)
- [ ] Update `tests/test_schemas.py` — canonical_id in expected_keys (QUAL-03)
- [ ] `tests/test_enrichment.py` — scheduler job registration test (QUAL-04)

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
