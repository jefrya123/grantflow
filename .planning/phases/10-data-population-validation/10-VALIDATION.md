---
phase: 10
slug: data-population-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | PIPE-03 | integration | `uv run python -m grantflow.ingest.sbir` | ✅ | ⬜ pending |
| 10-01-02 | 01 | 1 | PIPE-04 | integration | `uv run python -m grantflow.ingest.sam_gov` | ✅ | ⬜ pending |
| 10-01-03 | 01 | 1 | QUAL-01 | query | `uv run python -c "from grantflow.database import ..."` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 2 | STATE-02 | integration | `uv run python -m grantflow.ingest.state` | ✅ | ⬜ pending |
| 10-03-01 | 03 | 3 | QUAL-04 | integration | `uv run python -m grantflow.enrichment.run_enrichment` | ✅ | ⬜ pending |
| 10-03-02 | 03 | 3 | QUAL-01 | query | SQL spot-check on eligibility/category/funding labels | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test scaffolding needed — this phase validates by running real pipelines and querying results.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SAM.gov API key works | PIPE-04 | Requires real API key in .env | Set SAM_GOV_API_KEY, run ingestor, check >0 records |
| State scraper data quality | STATE-02 | Requires network access to state portals | Run scrapers, spot-check 5 records per state |
| LLM enrichment quality | QUAL-04 | Requires OPENAI_API_KEY and costs money | Run on 100 records, review tag quality |
| NC county grants | STATE-02 | New scraper, requires research | Identify NC grant portal, verify county-level data |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
