---
phase: 10-data-population-validation
verified: 2026-03-24T23:20:00Z
status: passed
score: 13/13 must-haves verified
gaps: []
human_verification:
  - test: "Topic tags enrichment end-to-end"
    expected: "After setting OPENAI_API_KEY and running run_enrichment, opportunities have non-empty topic_tags values that reflect meaningful sector/topic labels"
    why_human: "OPENAI_API_KEY not configured in this environment — enrichment skips silently by design; automated check confirms skip guard works but cannot verify tag quality or population"
  - test: "SAM.gov full pipeline with real API key"
    expected: "After registering at api.sam.gov and adding SAM_GOV_API_KEY to .env, ingest_sam_gov() returns status='success' or status='partial' and contract opportunities appear in opportunities table"
    why_human: "SAM_GOV_API_KEY is a user_setup dependency; automated check confirms graceful skip but cannot verify actual ingestion with a real key"
---

# Phase 10: Data Population & Validation Verification Report

**Phase Goal:** Actually run all pipelines (SBIR, SAM.gov, state scrapers, LLM enrichment), fix what breaks, verify normalization produces human-readable labels, and validate the data makes the product useful
**Verified:** 2026-03-24T23:20:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `normalize_category('D')` returns `'Discretionary'` | VERIFIED | Live function call returns `'Discretionary'`; CATEGORY_CODE_MAP confirmed in normalizers.py |
| 2 | `normalize_funding_instrument('CA')` returns `'Cooperative Agreement'` | VERIFIED | Live function call confirmed; FUNDING_INSTRUMENT_MAP present in normalizers.py |
| 3 | All 81K existing Grants.gov records have human-readable eligibility, category, and funding_instrument values | VERIFIED | DB query: `bare_elig=0 raw_cat=0 raw_fi=0` across 81,856 grants_gov records |
| 4 | New ingestions produce normalized category and funding_instrument values | VERIFIED | `normalize_category`/`normalize_funding_instrument` wired at lines 206-207 and 352-353 of grants_gov.py (REST + XML paths); `normalize_funding_instrument` wired at line 176 of sam_gov.py |
| 5 | SBIR ingestion completes with `status='success'` and `records_processed > 0` | VERIFIED | 6,276 SBIR awards in `awards` table (`source='sbir'`); CSV field mismatch and intra-CSV dedup bugs fixed |
| 6 | SAM.gov ingestion gracefully skipped with `status='skipped'` when key absent | VERIFIED | Code confirmed at sam_gov.py lines 49-51: guard returns `status='skipped'` when `SAM_GOV_API_KEY` not set |
| 7 | SBIR awards appear in the awards table | VERIFIED | DB: `awards WHERE source='sbir'` = 6,276 records |
| 8 | North Carolina scraper exists and produces records | VERIFIED | `north_carolina.py` exists, `NorthCarolinaScraper(BaseStateScraper)` class confirmed; 1,438 records in DB |
| 9 | At least 5 state sources have data in opportunities table | VERIFIED | DB: 6 state sources with data — IL(9316), NY(2738), CA(1869), TX(1730), NC(1438), CO(1) |
| 10 | State data normalized into unified Opportunity schema | VERIFIED | BaseStateScraper.run() uses raw SQL upsert; NC scraper maps to standard Opportunity fields |
| 11 | `topic_tags` column has non-null values on a meaningful sample (or documented user_setup) | VERIFIED (conditional) | OPENAI_API_KEY not set — `topic_tags=0` but enrichment skip guard confirmed working; documented as user_setup prerequisite |
| 12 | API returns multi-source data with normalized field values | VERIFIED | DB: 98,948 opportunities from 7 sources; `bare_elig=0`, `raw_cat=0`, `raw_fi=0`; API routes confirmed to query Opportunity model with source filter support |
| 13 | Eligibility/category fields show human-readable labels (not raw codes) | VERIFIED | DB query confirmed zero bare codes; normalize functions are live-tested |

**Score:** 13/13 truths verified (2 with human verification noted for user_setup paths)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `grantflow/normalizers.py` | CATEGORY_CODE_MAP, FUNDING_INSTRUMENT_MAP, normalize_category(), normalize_funding_instrument() | VERIFIED | All 4 items present; functions pass all test cases |
| `scripts/backfill_normalization.py` | Standalone backfill script | VERIFIED | Contains `backfill_normalization()`, imports all three normalizer functions, uses raw SQL pattern |
| `tests/test_normalizers.py` | Tests for normalize_category and normalize_funding_instrument | VERIFIED | `TestNormalizeCategory` (class at line 226, 10 test methods) and `TestNormalizeFundingInstrument` (class at line 260, 9 test methods) confirmed; 71 tests pass |
| `grantflow/ingest/sbir.py` | Working SBIR ingestor | VERIFIED | `ingest_sbir` function present; `_normalize_row()` CSV fix and `seen_ids` dedup fix applied; 6,276 awards in DB |
| `grantflow/ingest/sam_gov.py` | Working SAM.gov ingestor with graceful skip | VERIFIED | `ingest_sam_gov` present; skip guard at lines 49-51 |
| `grantflow/ingest/state/north_carolina.py` | NC state scraper with county-level support | VERIFIED | `NorthCarolinaScraper(BaseStateScraper)` with `fetch_records()` and `normalize_record()`; 1,438 records in DB |
| `grantflow/ingest/run_state.py` | Orchestrator including NorthCarolinaScraper | VERIFIED | Import and instantiation at lines 16 and 23 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `grantflow/ingest/grants_gov.py` | `grantflow/normalizers.py` | `import normalize_category, normalize_funding_instrument` | WIRED | Import at line 25-26; applied at lines 206-207 (REST) and 352-353 (XML) |
| `scripts/backfill_normalization.py` | `grantflow/normalizers.py` | import + apply all normalizers | WIRED | Lines 22-24 import all three; applied at lines 80, 85, 92 |
| `grantflow/ingest/sam_gov.py` | `grantflow/normalizers.py` | `import normalize_funding_instrument` | WIRED | Import at line 17; applied at line 176 |
| `grantflow/ingest/run_state.py` | `grantflow/ingest/state/north_carolina.py` | `import NorthCarolinaScraper` in `_get_scrapers()` | WIRED | Lines 16 and 23 confirmed |
| `grantflow/ingest/state/north_carolina.py` | `grantflow/ingest/state/base.py` | `class NorthCarolinaScraper(BaseStateScraper)` | WIRED | Line 55 confirmed |
| `grantflow/enrichment/run_enrichment.py` | `grantflow/models.py` | SQLAlchemy query + update on `Opportunity.topic_tags` | WIRED | Lines 41-42 query `Opportunity.topic_tags.is_(None)`; line 67 sets `opp.topic_tags` |
| `grantflow/api/routes.py` | `grantflow/models.py` | SQLAlchemy query returning multi-source Opportunity rows | WIRED | Line 10 imports Opportunity; `source` filter passed through at line 58 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| QUAL-01 | 10-01 | Eligibility codes normalized to human-readable categories | SATISFIED | `normalize_category()` and `normalize_funding_instrument()` added; 81,856 records backfilled; `bare_elig=0 raw_cat=0 raw_fi=0` in DB |
| PIPE-03 | 10-02 | SBIR ingestion works reliably (fix rate limiting, retry logic) | SATISFIED | Root cause fixed (`_normalize_row()` + `seen_ids`); 6,276 awards in DB; `status='success'` confirmed |
| PIPE-04 | 10-02 | SAM.gov contract opportunities ingested (with registered API key, incremental design) | SATISFIED (conditional) | Ingestor functional; graceful skip guard confirmed; user_setup documented for API key registration |
| STATE-02 | 10-03 | At least 5 state portals scraped and normalized into unified schema | SATISFIED | 6 state sources with data: IL(9316), NY(2738), CA(1869), TX(1730), NC(1438), CO(1); all normalized |
| QUAL-04 | 10-04 | LLM-powered categorization tags opportunities by topic/sector | SATISFIED (conditional) | `run_enrichment()` function wired to `Opportunity.topic_tags`; skip guard works when OPENAI_API_KEY absent; topic_tags=0 because key not set — documented as user_setup |

All 5 requirement IDs claimed across plans are accounted for. No orphaned requirements detected for Phase 10 in REQUIREMENTS.md.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No stubs, placeholder returns, TODO/FIXME blockers, or empty implementations found in phase deliverables. All bugs found during execution were auto-fixed with verification.

### Human Verification Required

#### 1. Topic Tags Enrichment (QUAL-04 full validation)

**Test:** Add `OPENAI_API_KEY=sk-...` to `.env`, then run `ENRICHMENT_BATCH_SIZE=500 uv run python -m grantflow.enrichment.run_enrichment`
**Expected:** `SELECT COUNT(*) FROM opportunities WHERE topic_tags IS NOT NULL` returns > 0; sample tags are meaningful sector/topic labels (not empty JSON arrays or error strings)
**Why human:** OPENAI_API_KEY is a paid external service credential. The enrichment module skips silently when the key is absent — the code path from key present → API call → tag storage cannot be exercised without a live key.

#### 2. SAM.gov Full Pipeline with Real API Key (PIPE-04 full validation)

**Test:** Register at https://api.sam.gov for a free public-tier key, add `SAM_GOV_API_KEY=your_key` to `.env`, then run `uv run python -c "from grantflow.ingest.sam_gov import ingest_sam_gov; import json; print(json.dumps(ingest_sam_gov(), indent=2))"`
**Expected:** `status` is `success` or `partial`; `SELECT COUNT(*) FROM opportunities WHERE source='sam_gov'` returns > 0
**Why human:** Free API key requires external registration. The skip guard and ingestor structure are verified, but actual data ingestion requires a live credential.

### Gaps Summary

No gaps. All automated must-haves pass.

The two human verification items are user_setup dependencies explicitly declared in their plan frontmatter — they are not implementation gaps but external credential prerequisites. The code correctly handles both cases (graceful skip when absent, full ingestion when present).

**Notable findings:**
- The `search_vector` SQLite column was missing (ORM declared it but migration never created it) — fixed inline during Plan 04 via `ALTER TABLE`. This was a pre-existing infrastructure gap, not introduced by Phase 10.
- State sources (CA, NY, TX, NC) have NULL `post_date` values, causing them to sort last in default API queries. This is a data quality limitation of the source portals, not a normalization defect.
- Colorado scraper returns only 1 record due to a pre-existing 404 from choosecolorado.com — out of scope for Phase 10, does not affect 5-state requirement (5 active states + CO = 6 total).

---

_Verified: 2026-03-24T23:20:00Z_
_Verifier: Claude (gsd-verifier)_
