---
phase: 02-pipeline-hardening
verified: 2026-03-24T00:00:00Z
status: passed
score: 8/8 must-haves verified
re_verification: false
---

# Phase 02: Pipeline Hardening Verification Report

**Phase Goal:** All federal data sources ingest automatically on a daily schedule with monitoring that detects and alerts on stale or broken data before any customer notices
**Verified:** 2026-03-24
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Daily schedule fires run_all_ingestion() automatically at 02:00 UTC | VERIFIED | `app.py:25-28` — `AsyncIOScheduler` with `CronTrigger(hour=2, minute=0, timezone="UTC")` registered in FastAPI lifespan |
| 2 | Every ingest run writes a PipelineRun row with full stats | VERIFIED | `run_all.py:24-27` — `_write_pipeline_run()` called per source; `PipelineRun` model has all required fields |
| 3 | SBIR retries up to 3x on network errors with exponential backoff | VERIFIED | `sbir.py:174,188` — `for attempt in range(3)` with `time.sleep(2 ** attempt)` |
| 4 | SAM.gov ingest runs incrementally and skips cleanly without API key | VERIFIED | `sam_gov.py:70-72` — `if not SAM_GOV_API_KEY: ... stats["status"] = "skipped"`; `sam_gov.py:103-108` — PipelineRun query for last success |
| 5 | Grants.gov tries REST first, falls back to XML on failure | VERIFIED | `grants_gov.py:458-482` — `_ingest_via_rest()` attempted first; returns None on 5xx or < MIN_REST_THRESHOLD; `_ingest_via_xml()` called on None |
| 6 | Staleness monitor alerts (log ERROR) when any source > 48h without success | VERIFIED | `monitor.py:68,130` — `STALE_THRESHOLD_HOURS=48`; `logger.error("stale_source_detected", ...)` in `check_staleness()`; SMTP email via `_send_alert_email()` |
| 7 | Health endpoint reports per-source freshness | VERIFIED | `routes.py:241,246` — `get_freshness_report(db)` called; `"source_freshness": freshness` in response dict |
| 8 | Opportunities cross-referenced to Awards via normalized CFDA numbers | VERIFIED | `cfda_link.py:14,53` — `normalize_cfda()` + `link_opportunities_to_awards()`; wired in `run_all.py:154-156` |

**Score:** 8/8 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `grantflow/pipeline/__init__.py` | Pipeline package init | VERIFIED | Exists |
| `grantflow/pipeline/logging.py` | `configure_structlog()` + `bind_source_logger()` | VERIFIED | Both functions present; `structlog.configure()` called; JSON in production, ConsoleRenderer in dev |
| `alembic/versions/0003_pipeline_run_table.py` | Migration adding pipeline_runs table | VERIFIED | `op.create_table('pipeline_runs', ...)` present; `down_revision='0002'` |
| `grantflow/models.py` | `PipelineRun` SQLAlchemy model | VERIFIED | `class PipelineRun` at line 111; all fields present including `records_failed`, `error_message`, `extra` |
| `grantflow/app.py` | APScheduler `AsyncIOScheduler` in lifespan | VERIFIED | Lines 9-10 import; lines 25-28 register cron job; `scheduler.shutdown()` on teardown |
| `grantflow/ingest/run_all.py` | Orchestrator writing PipelineRun rows; structlog; sam_gov step | VERIFIED | `_write_pipeline_run()` helper; `ingest_sam_gov` as step 4; `check_staleness()` and `link_opportunities_to_awards()` at end |
| `grantflow/ingest/grants_gov.py` | `_ingest_via_rest()` + `_ingest_via_xml()` dual-source strategy | VERIFIED | Both private helpers present; strategy selector in `ingest_grants_gov()`; `MIN_REST_THRESHOLD=100`; FTS rebuild removed |
| `grantflow/ingest/usaspending.py` | Incremental mode; `bind_source_logger`; `records_failed` | VERIFIED | PipelineRun query at lines 127-132; `incremental_start` logic present; `bind_source_logger("usaspending")` |
| `grantflow/ingest/sbir.py` | Retry logic; `hashlib` at module top; `opportunity_status` derived | VERIFIED | `import hashlib` at line 4; retry loop lines 174-188; `opportunity_status` derived from `close_date` at line 221 |
| `grantflow/ingest/sam_gov.py` | SAM.gov ingestor; skip without key; 429 rate limit handling | VERIFIED | Skip at lines 70-72; 429 check at line 142; rate limit flag propagated to stats |
| `grantflow/pipeline/monitor.py` | `check_staleness()` + `get_freshness_report()` | VERIFIED | Both functions present; `STALE_THRESHOLD_HOURS=48`; SMTP email alert via `_send_alert_email()` |
| `grantflow/pipeline/cfda_link.py` | `normalize_cfda()` + `link_opportunities_to_awards()` | VERIFIED | Both functions present; handles hyphens, spaces, leading zeros, padding |
| `grantflow/config.py` | `SAM_GOV_API_KEY`, `SAM_GOV_API_BASE`, `GRANTS_GOV_REST_API_BASE`, `GRANTS_GOV_USE_REST` | VERIFIED | All four vars present at lines 17-26 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.py` | `run_all_ingestion` | `scheduler.add_job(run_all_ingestion, CronTrigger)` | WIRED | `app.py:27` — lambda wraps `run_all_ingestion` in executor |
| `run_all.py` | `grantflow/models.PipelineRun` | `session.add(PipelineRun(...))` | WIRED | `_write_pipeline_run()` helper builds and commits `PipelineRun` rows per source |
| `sam_gov.py` | `api.sam.gov` | `httpx.get` with `api_key` param | WIRED | `sam_gov.py:17` — `SEARCH_ENDPOINT = f"{SAM_GOV_API_BASE}/search"`; called with params including `api_key` |
| `run_all.py` | `sam_gov.py` | `results['sam_gov'] = ingest_sam_gov()` | WIRED | `run_all.py:104` — `results["sam_gov"] = ingest_sam_gov()` |
| `grants_gov.py` | `search2` REST endpoint | `_ingest_via_rest()` using `httpx.post` | WIRED | `grants_gov.py:28` — `SEARCH2_ENDPOINT`; function calls `httpx.post(SEARCH2_ENDPOINT, ...)` |
| `grants_gov.py` | `_find_extract_url()` | fallback when REST returns None | WIRED | `grants_gov.py:482` — `xml_stats = _ingest_via_xml(session)` called when `rest_stats is None` |
| `monitor.py` | `grantflow/models.PipelineRun` | `func.max(PipelineRun.completed_at)` query | WIRED | `monitor.py:39-42` — SQLAlchemy select with source + status='success' filter |
| `cfda_link.py` | `grantflow/models.Award` | `Award.cfda_numbers.contains(norm_cfda)` | WIRED | `cfda_link.py:107-108` — session.query(Award) with contains filter |
| `run_all.py` | `monitor.py` | `check_staleness()` at end of pipeline | WIRED | `run_all.py:145-146` — imported and called after all sources complete |
| `routes.py` | `monitor.py` | `get_freshness_report(db)` in health handler | WIRED | `routes.py:9,241,246` — imported at top; called in health endpoint; included in response |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PIPE-01 | 02-02 | Grants.gov ingestion runs automatically on daily schedule | SATISFIED | APScheduler fires `run_all_ingestion()` including grants_gov step daily at 02:00 UTC |
| PIPE-02 | 02-02 | USAspending ingestion runs automatically with incremental updates | SATISFIED | `usaspending.py` queries last successful PipelineRun; adjusts `start_date` to `completed_at - 2 days` |
| PIPE-03 | 02-02 | SBIR ingestion works reliably (fix rate limiting, retry logic) | SATISFIED | 3-attempt retry with exponential backoff in `sbir.py`; `opportunity_status` derived from `close_date` |
| PIPE-04 | 02-03 | SAM.gov contract opportunities ingested (incremental, with API key) | SATISFIED | `sam_gov.py` full ingestor; incremental from last success; 429 rate limit clean stop; skip without key |
| PIPE-05 | 02-05 | Pipeline monitoring detects stale data (no update in 48h triggers alert) | SATISFIED | `monitor.py` `check_staleness()` logs ERROR + sends email; called after every pipeline run |
| PIPE-06 | 02-01 | Pipeline logs ingestion stats (records added/updated/failed per run) | SATISFIED | PipelineRun model captures `records_added`, `records_updated`, `records_failed`; written after every source |
| PIPE-07 | 02-05 | Cross-source joining links opportunities to historical awards via CFDA/ALN | SATISFIED | `cfda_link.py` normalizes CFDA format and links opportunities to awards; run post-ingest |
| PIPE-08 | 02-04 | Grants.gov ingestion supports both XML extract and new REST API | SATISFIED | `_ingest_via_rest()` + `_ingest_via_xml()` dual-source strategy; `GRANTS_GOV_USE_REST` flag for REST-only mode |

All 8 PIPE requirements satisfied. No orphaned requirements found.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `grantflow/ingest/usaspending.py` | 71 | `return {}` | INFO | Guard in row mapper helper (`_map_award_row`) — not a stub; returns empty dict when `award_id_raw` is blank so the caller can skip the row. Correct behavior. |

No blockers or warnings found.

**Note on plan deviation:** Plan 02-02 specified using `awarding_agency.toptier_agency.abbreviation` from the JSON API response for `agency_code` in `usaspending.py`. The actual implementation instead reads `agency_code` from the CSV field `"Awarding Sub Agency"` directly (the ingestor uses a CSV download, not the awards JSON endpoint). The `re.sub` slug is used only for the `Agency` table upsert key, not for individual award rows. This is a non-blocking deviation — the intent (avoid lossy truncation) is achieved differently and without data loss.

---

### Human Verification Required

#### 1. APScheduler Fires at 02:00 UTC in Production

**Test:** Deploy to production server and wait for 02:00 UTC trigger, or manually invoke via `asyncio.get_event_loop().run_in_executor(None, run_all_ingestion)` and observe APScheduler logs.
**Expected:** Log line "APScheduler started — daily ingestion at 02:00 UTC" appears at startup; `run_all_ingestion` executes once daily.
**Why human:** Cannot verify scheduler actually fires without a running server and wall-clock time passage.

#### 2. Email Alert Delivery

**Test:** Set `GRANTFLOW_ALERT_EMAIL=test@example.com` and `SMTP_HOST`/`SMTP_PORT` to a real SMTP server. Insert a PipelineRun row with `completed_at` 50h ago and `status='success'` for one source. Call `check_staleness()`.
**Expected:** An alert email is received; SMTP failure (wrong host) logs error but does not raise or crash.
**Why human:** SMTP delivery requires a real mail server; cannot verify via grep.

#### 3. Grants.gov REST API Live Response

**Test:** With `GRANTS_GOV_USE_REST=true`, trigger ingestion and observe logs.
**Expected:** REST path is taken; log shows `"rest_succeeded"` with record count >= 100; opportunities appear in DB with `source="grants_gov"`.
**Why human:** `search2` API is labeled "early development" and may return different record counts or fail; live behavior cannot be confirmed statically.

---

### Test Suite

All 35 tests pass (`uv run pytest tests/ -x -q` — 35 passed in 0.26s).

Test files added this phase:
- `tests/test_cfda_link.py` — `normalize_cfda()` variant handling
- `tests/test_grants_gov_rest.py` — REST fallback behavior
- `tests/test_monitor.py` — freshness report and staleness detection
- `tests/test_sam_gov.py` — skip-without-key behavior

---

### Summary

Phase 02 goal is **achieved**. All 8 PIPE requirements are satisfied:

- The daily schedule is wired via APScheduler in the FastAPI lifespan (02:00 UTC, UTC-correct, misfire-tolerant).
- All four federal sources (Grants.gov, USAspending, SBIR, SAM.gov) are integrated into the pipeline and write PipelineRun rows.
- Monitoring (`check_staleness()`) fires after every pipeline run and logs ERROR + sends email alerts for any source missing a successful run in 48h.
- The health endpoint exposes per-source freshness so operators can detect stale data immediately.
- CFDA normalization and cross-linking are wired in post-ingest.
- Zero regressions: all 35 tests pass.

---

_Verified: 2026-03-24_
_Verifier: Claude (gsd-verifier)_
