---
phase: 7
slug: gtm-enrichment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_analytics.py tests/test_enrichment.py tests/test_gtm_pages.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_analytics.py tests/test_enrichment.py tests/test_gtm_pages.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 0 | GTM-01 | integration | `uv run pytest tests/test_gtm_pages.py::test_landing_page -x` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 0 | GTM-02 | integration | `uv run pytest tests/test_gtm_pages.py::test_pricing_page -x` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 0 | GTM-03 | integration | `uv run pytest tests/test_gtm_pages.py::test_playground_page -x` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | GTM-04 | integration | `uv run pytest tests/test_analytics.py::test_event_recorded -x` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 1 | QUAL-04 | unit (mocked) | `uv run pytest tests/test_enrichment.py::test_tag_opportunity_mock -x` | ❌ W0 | ⬜ pending |
| 07-03-02 | 03 | 1 | QUAL-04 | integration | `uv run pytest tests/test_enrichment.py::test_topic_filter -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_gtm_pages.py` — covers GTM-01, GTM-02, GTM-03 (landing, pricing, playground)
- [ ] `tests/test_analytics.py` — covers GTM-04 (middleware event recording)
- [ ] `tests/test_enrichment.py` — covers QUAL-04 (mocked LLM tag + topic filter)

*Existing test infrastructure (conftest.py, pytest config) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Landing page visual layout and copy quality | GTM-01 | CSS/copy review not automatable | Open / in browser, verify value prop is clear and pricing link is visible |
| Pricing tier display and layout | GTM-02 | Visual layout correctness | Open /pricing, verify 3 tiers displayed with coverage-based descriptions |
| Playground interactive JS functionality | GTM-03 | JS execution requires browser | Open /playground, run a sample query, verify results display |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
