---
phase: 01-foundation
verified: 2026-03-24T00:00:00Z
status: gaps_found
score: 11/12 must-haves verified
gaps:
  - truth: "No FTS5 virtual table references remain in application code"
    status: failed
    reason: "Two ingest files still write to the SQLite-only opportunities_fts virtual table. These were not covered by any plan's files_modified list. Running ingestion against PostgreSQL will crash because the table does not exist."
    artifacts:
      - path: "grantflow/ingest/grants_gov.py"
        issue: "Lines 239-242: DELETE FROM opportunities_fts + INSERT INTO opportunities_fts after upsert batch. Will raise OperationalError on PostgreSQL."
      - path: "grantflow/ingest/run_all.py"
        issue: "Lines 21-25: _rebuild_fts() function executes DELETE/INSERT on opportunities_fts. Called as part of the full ingestion run."
    missing:
      - "Remove or gate the FTS5 rebuild block in grants_gov.py behind a SQLite dialect check (or remove entirely — PostgreSQL trigger handles this automatically)"
      - "Remove or gate _rebuild_fts() in run_all.py and its call site behind a SQLite dialect check"
human_verification:
  - test: "Run alembic upgrade head against a live PostgreSQL instance"
    expected: "Both migrations apply cleanly; opportunities, awards, agencies, ingestion_log, search_vector column, GIN index, and trigger all exist"
    why_human: "No PostgreSQL instance available in CI environment to execute the migration end-to-end"
  - test: "Run alembic downgrade -1 against a live PostgreSQL instance"
    expected: "Migration 0002 rolls back cleanly, dropping search_vector, GIN index, trigger function"
    why_human: "Requires live PostgreSQL"
  - test: "Submit a search query with ?q=climate against a PostgreSQL-backed instance"
    expected: "Results returned under 100ms using the GIN index (not a sequential scan)"
    why_human: "Requires live data and EXPLAIN ANALYZE to confirm index usage"
---

# Phase 1: Foundation Verification Report

**Phase Goal:** The application runs on PostgreSQL with schema migration tooling, full-text search, and a health endpoint — providing a stable, production-capable base for all subsequent work
**Verified:** 2026-03-24
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Application connects to PostgreSQL when GRANTFLOW_DATABASE_URL is postgres:// URL | VERIFIED | `database.py` detects prefix at module load, builds `postgresql+psycopg2://` URL, creates sync engine with `pool_pre_ping=True` |
| 2 | Application still starts and connects to SQLite when no DATABASE_URL is set | VERIFIED | `config.py` defaults to `sqlite:///grantflow.db`; `database.py` SQLite branch retains WAL pragmas unchanged |
| 3 | Alembic can generate and apply migrations against the PostgreSQL database | VERIFIED | `alembic.ini` + `env.py` both present and correctly wired; `env.py` injects psycopg2 URL at runtime |
| 4 | Running 'alembic upgrade head' creates all tables from models.py | VERIFIED (static) | Migration 0001 has `op.create_table()` for all 4 tables with correct columns and indexes; 0002 chains correctly via `down_revision='0001'` |
| 5 | Running 'alembic downgrade -1' rolls back the initial migration without error | VERIFIED (static) | Both `downgrade()` functions present and correct; 0002 drops trigger, function, index, column; 0001 drops all 4 tables |
| 6 | Full-text search uses PostgreSQL tsvector + GIN index (not FTS5 virtual table) | VERIFIED (routes) | `api/routes.py` and `web/routes.py` both use `to_tsquery("english", q)` against `Opportunity.search_vector`; LIKE fallback for SQLite |
| 7 | The tsvector column is updated automatically via a DB trigger on INSERT/UPDATE | VERIFIED (static) | Migration 0002 creates `opportunities_search_vector_update()` function and `BEFORE INSERT OR UPDATE` trigger with backfill |
| 8 | SQLite dev path retains LIKE-based fallback search | VERIFIED | Both route files check `_DB_URL.startswith("postgresql")` and fall through to `ilike()` on title/description/agency_name |
| 9 | No FTS5 virtual table references remain in application code | FAILED | `grantflow/ingest/grants_gov.py` lines 239-242 and `grantflow/ingest/run_all.py` lines 21-25 still execute DELETE/INSERT against `opportunities_fts`. Will crash on PostgreSQL. |
| 10 | GET /api/v1/health returns 200 with a JSON body | VERIFIED | Route registered at `@router.get("/health")` on `APIRouter(prefix="/api/v1")`; returns dict with status/sources/checked_at |
| 11 | Health response includes last_ingestion_at, record_counts, overall_status, stale detection | VERIFIED | Implementation queries latest IngestionLog per source, counts Opportunity rows, computes staleness at 48h threshold; 5/5 tests pass |
| 12 | The endpoint works with no ingestion_log rows (returns nulls, not 500) | VERIFIED | `test_health_empty_db` passes: empty DB returns `{"status":"ok","sources":{},"checked_at":"..."}` |

**Score:** 11/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic.ini` | Alembic config pointing to grantflow/database.py engine | VERIFIED | `script_location = %(here)s/alembic`; URL comment only (no hardcoded credentials) |
| `alembic/env.py` | Migration env using Base.metadata and DATABASE_URL from config | VERIFIED | Imports `Base` from `grantflow.models`, `DATABASE_URL` from `grantflow.config`; builds psycopg2 URL; both offline/online modes |
| `alembic/versions/0001_initial_schema.py` | Initial migration covering all 4 tables | VERIFIED | All 4 tables created with correct columns/indexes; clean downgrade |
| `alembic/versions/0002_add_tsvector_fts.py` | Migration adding search_vector + GIN index + trigger | VERIFIED | `down_revision='0001'`; column, GIN index, trigger function, backfill UPDATE; full downgrade |
| `grantflow/database.py` | PostgreSQL-compatible engine, SQLite fallback | VERIFIED | Dual-dialect with correct URL rewriting; `pool_pre_ping=True`; WAL pragmas on SQLite path |
| `grantflow/models.py` | `search_vector` column (tsvector, SQLite-compatible) | VERIFIED | `TSVECTORType` TypeDecorator returns TSVECTOR on PostgreSQL, Text on SQLite; `search_vector` column present |
| `grantflow/api/routes.py` | FTS via to_tsquery(); health endpoint; IngestionLog imported | VERIFIED | Both FTS paths present; `/health` fully implemented with stale logic; `IngestionLog` in top-level imports |
| `grantflow/web/routes.py` | Same tsvector FTS switch as API routes | VERIFIED | Identical dialect-branched FTS pattern; no FTS5 references |
| `tests/conftest.py` | pytest fixtures: test client, SQLite test DB | VERIFIED | `test_engine` (session), `db_session` (function/rollback), `client` (dependency_overrides) |
| `tests/test_health.py` | 5 tests: empty DB, recent ingestion, stale, error, record counts | VERIFIED | 5/5 tests pass (confirmed by `uv run pytest tests/test_health.py -v`) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `alembic/env.py` | `grantflow/models.py` | `from grantflow.models import Base` | WIRED | Line 9; `target_metadata = Base.metadata` line 31 |
| `grantflow/database.py` | `grantflow/config.py` | `from grantflow.config import DATABASE_URL` | WIRED | Line 3 |
| `grantflow/api/routes.py` | `opportunities.search_vector` | `to_tsquery()` filter | WIRED | Lines 34-38; `Opportunity.search_vector.op("@@")(func.to_tsquery("english", q))` |
| `alembic/versions/0002_add_tsvector_fts.py` | opportunities table | `op.add_column` + GIN + trigger | WIRED | Lines 19-67; column, index, trigger function, attachment, backfill all present |
| `grantflow/api/routes.py` | `grantflow/models.py IngestionLog` | SQLAlchemy query on ingestion_log table | WIRED | `IngestionLog` in top-level import (line 6); queried at lines 197-205 |
| `tests/test_health.py` | `grantflow/app.py` | `TestClient` from conftest fixture | WIRED | `conftest.py` line 6 imports `app` from `grantflow.app`; `TestClient(app)` line 46 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FOUND-01 | 01-01-PLAN.md | Database migrated from SQLite to PostgreSQL with Alembic migrations | SATISFIED | `database.py` dual-dialect engine; `alembic/env.py`; migrations 0001+0002 present and wired |
| FOUND-02 | 01-02-PLAN.md | Full-text search uses PostgreSQL tsvector + GIN index (replacing FTS5) | PARTIAL | Routes use `to_tsquery()` correctly. However, `grantflow/ingest/grants_gov.py` and `grantflow/ingest/run_all.py` still rebuild `opportunities_fts` — the old SQLite FTS5 table — which will crash on PostgreSQL and pollute ingestion runs. The query path is correct; the write path is not. |
| FOUND-03 | 01-01-PLAN.md | Environment config supports production PostgreSQL connection | SATISFIED | `config.py` uses `GRANTFLOW_DATABASE_URL` env var; `database.py` correctly constructs psycopg2 URL from it |
| FOUND-04 | 01-03-PLAN.md | Health endpoint returns pipeline freshness and record counts | SATISFIED | `/api/v1/health` returns `{status, sources: {last_ingestion_at, last_status, records_added_last_run, record_count, stale}, checked_at}`; 5/5 tests pass |

### Anti-Patterns Found

| File | Lines | Pattern | Severity | Impact |
|------|-------|---------|----------|--------|
| `grantflow/ingest/grants_gov.py` | 239-242 | `DELETE FROM opportunities_fts` + `INSERT INTO opportunities_fts` | Blocker | Crashes on PostgreSQL — `opportunities_fts` table does not exist in PostgreSQL schema. Any ingestion run against production DB will fail at this point. |
| `grantflow/ingest/run_all.py` | 21-25 | `_rebuild_fts()` function targeting `opportunities_fts` | Blocker | Same crash vector. `run_all_ingestion()` calls `_rebuild_fts()` which will fail on any PostgreSQL connection. |

### Human Verification Required

#### 1. Alembic upgrade head against live PostgreSQL

**Test:** Set `GRANTFLOW_DATABASE_URL` to a PostgreSQL connection string and run `uv run alembic upgrade head`
**Expected:** Both migrations apply cleanly; `\d opportunities` in psql shows `search_vector` column of type `tsvector`, GIN index `ix_opportunities_search_vector`, and trigger `opportunities_search_vector_trigger`
**Why human:** No PostgreSQL instance available in this environment

#### 2. Alembic downgrade against live PostgreSQL

**Test:** `uv run alembic downgrade -1` after upgrade
**Expected:** Migration 0002 rolls back — search_vector column, GIN index, and trigger function all removed; `\d opportunities` shows no search_vector
**Why human:** Requires live PostgreSQL

#### 3. FTS query latency against GIN index

**Test:** With 80K+ rows loaded, run `GET /api/v1/opportunities/search?q=climate`
**Expected:** Results in under 100ms; `EXPLAIN ANALYZE` shows `Bitmap Index Scan on ix_opportunities_search_vector` (not `Seq Scan`)
**Why human:** Requires live PostgreSQL with data loaded

### Gaps Summary

One gap blocks complete goal achievement:

**Ingest pipeline still targets the SQLite FTS5 virtual table.** The API and web route search paths were correctly updated to use PostgreSQL tsvector (Plan 02 scope). However, `grantflow/ingest/grants_gov.py` and `grantflow/ingest/run_all.py` were not in any plan's `files_modified` list and retain their FTS5 rebuild blocks. When the pipeline runs against PostgreSQL, the `opportunities_fts` table does not exist, causing a hard crash at the end of each ingestion run.

This violates FOUND-02's intent: the FTS5 removal is incomplete. The query path is clean; the write path is not.

The fix is straightforward — either remove the FTS5 rebuild blocks entirely (PostgreSQL's BEFORE INSERT trigger handles `search_vector` automatically) or gate them behind a SQLite dialect check.

---

_Verified: 2026-03-24_
_Verifier: Claude (gsd-verifier)_
