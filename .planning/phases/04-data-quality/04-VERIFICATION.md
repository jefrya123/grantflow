---
phase: 04-data-quality
verified: 2026-03-24T19:30:00Z
status: gaps_found
score: 6/7 must-haves verified
re_verification: false
gaps:
  - truth: "award_floor and award_ceiling values with floor > ceiling or negative values are set to None rather than stored"
    status: partial
    reason: "validate_award_amounts is imported in sbir.py but never called. SBIR solicitations do not include award_floor/award_ceiling fields in their record dict, so the import is dead code. grants_gov.py correctly applies validation at both parse paths. usaspending.py does not expose floor/ceiling fields (uses award_amount instead), which is acceptable. The gap is sbir.py's unused import — if SBIR data ever gains floor/ceiling fields they would bypass validation."
    artifacts:
      - path: "grantflow/ingest/sbir.py"
        issue: "validate_award_amounts imported on line 21 but no call site exists anywhere in the file. SBIR records never populate award_floor or award_ceiling."
    missing:
      - "Either call validate_award_amounts on sbir.py solicitation records (adding award_floor/ceiling fields from SBIR data if available), or remove the unused import if SBIR truly has no floor/ceiling data"
---

# Phase 4: Data Quality Verification Report

**Phase Goal:** Normalize eligibility codes, agency names, dates, amounts, and deduplicate across sources
**Verified:** 2026-03-24T19:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Eligibility codes stored in opportunities.eligible_applicants are human-readable strings, not raw CFDA codes | VERIFIED | ELIGIBILITY_CODE_MAP with 17 entries in normalizers.py lines 14-36; called in grants_gov.py lines 200, 342 and sbir.py line 226; tests pass |
| 2 | Agency names are consistent across sources — canonical form applied via AGENCY_NAME_MAP | VERIFIED | AGENCY_NAME_MAP (30+ entries, ~56-line block) in normalizers.py; normalize_agency_name called in grants_gov.py lines 203, 345; sbir.py line 224; usaspending.py line 87 |
| 3 | All date fields are ISO 8601 (YYYY-MM-DD) across Grants.gov, SBIR, and USAspending | VERIFIED | normalize_date called throughout all three ingest modules; local _normalize_date and _parse_date removed from grants_gov.py and sbir.py; 12 date tests pass including garbage-returns-None contract |
| 4 | award_floor and award_ceiling values with floor > ceiling or negative values are set to None | PARTIAL | grants_gov.py applies validate_award_amounts at both parse paths (lines 204, 346); sbir.py imports but never calls it — SBIR records have no award_floor/ceiling fields; usaspending.py uses award_amount instead (no floor/ceiling) |
| 5 | Same grant appearing in Grants.gov and SBIR is assigned the same canonical_id | VERIFIED | make_canonical_id uses normalized opportunity_number (strip/uppercase/collapse hyphens) as primary key; determinism tests pass; 14/14 make_canonical_id tests pass |
| 6 | canonical_id is present on all Opportunity records (non-null after migration + backfill) | VERIFIED | Migration 0005 adds column; models.py line 61 defines it; run_all.py lines 160-164 call assign_canonical_ids after each ingest; summary reports 81,856 records backfilled with 0 NULLs |
| 7 | A weekly dedup report query reveals cross-source duplicates without modifying data | VERIFIED | find_duplicate_groups in dedup.py line 38 is read-only by contract; test_does_not_modify_data passes; returns list of dicts with canonical_id, count, ids, sources |

**Score: 6/7 truths verified** (1 partial — sbir.py award amount validation)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `grantflow/normalizers.py` | All normalization utilities | VERIFIED | 221 lines; exports normalize_date (line 111), validate_award_amounts (line 131), normalize_eligibility_codes (line 159), normalize_agency_name (line 203); no DB imports |
| `tests/test_normalizers.py` | Unit tests for all normalizer functions | VERIFIED | 207 lines; 50 tests across TestNormalizeDate, TestValidateAwardAmounts, TestNormalizeEligibilityCodes, TestNormalizeAgencyName; all pass |
| `grantflow/dedup.py` | Canonical ID and duplicate detection | VERIFIED | 120 lines; exports make_canonical_id (line 11), find_duplicate_groups (line 38), assign_canonical_ids (line 67); hashlib at module level |
| `alembic/versions/0005_add_canonical_id.py` | Migration adding canonical_id column | VERIFIED | Exists; upgrade adds canonical_id TEXT + ix_opportunities_canonical_id index; downgrade present; numbered 0005 (not 0003 as planned — 0003/0004 pre-claimed) |
| `tests/test_dedup.py` | Dedup unit tests | VERIFIED | 215 lines; 20 tests covering normalization, fallback, determinism, read-only contract; all pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `grantflow/ingest/grants_gov.py` | `grantflow/normalizers.py` | `from grantflow.normalizers import` (line 21) | WIRED | All four functions imported and called at parse time in both REST and XML paths |
| `grantflow/ingest/sbir.py` | `grantflow/normalizers.py` | `from grantflow.normalizers import` (line 17) | WIRED | normalize_date, normalize_eligibility_codes, normalize_agency_name called; validate_award_amounts imported but not called |
| `grantflow/ingest/usaspending.py` | `grantflow/normalizers.py` | `from grantflow.normalizers import` (line 13) | WIRED | normalize_date and normalize_agency_name imported and called; validate_award_amounts not imported (usaspending has no floor/ceiling fields) |
| `grantflow/ingest/run_all.py` | `grantflow/dedup.py` | `from grantflow.dedup import assign_canonical_ids` (line 160) | WIRED | Lazy import inside pipeline function; called line 163 with its own SessionLocal; result logged |
| `grantflow/models.py` | `alembic/versions/0005_add_canonical_id.py` | canonical_id column definition | WIRED | models.py line 61: `canonical_id = Column(Text, nullable=True, index=True)`; migration applies matching schema |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| QUAL-01 | 04-01 | Eligibility codes normalized to human-readable categories | SATISFIED | ELIGIBILITY_CODE_MAP with 17 codes; normalize_eligibility_codes wired into grants_gov.py and sbir.py; 11 dedicated tests pass |
| QUAL-02 | 04-01 | Agency names/codes normalized across all sources | SATISFIED | AGENCY_NAME_MAP (30+ variants); normalize_agency_name wired into all three ingest modules; 11 dedicated tests pass; USAspending agency slug bug fixed |
| QUAL-03 | 04-02 | Duplicate opportunities detected and merged across sources | SATISFIED | canonical_id assigned to all 81,856 records; same opportunity_number across sources produces identical canonical_id; find_duplicate_groups available for audit |
| QUAL-05 | 04-01 | Date fields consistently ISO 8601 across all sources | SATISFIED | normalize_date wired into all three ingest modules; local _normalize_date/_parse_date removed; garbage returns None not raw value; 12 date tests pass |
| QUAL-06 | 04-01 | Award amounts validated (floor <= ceiling, no negative values) | PARTIAL | validate_award_amounts implemented and tested correctly; wired into grants_gov.py both parse paths; sbir.py imports but never calls it (no floor/ceiling fields in SBIR records); usaspending.py uses award_amount (no floor/ceiling) |

**QUAL-04 is correctly assigned to Phase 7 (GTM + Enrichment) — not a Phase 4 requirement, not orphaned.**

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `grantflow/ingest/sbir.py` | `validate_award_amounts` imported but never called (line 21) | Warning | Dead import; if SBIR data ever gains floor/ceiling fields they would bypass validation silently |

No TODO/FIXME/placeholder comments found in any phase 4 files. No stub implementations detected. No empty handlers. hashlib imported at module level in dedup.py (not inside functions — CONCERNS.md pattern followed correctly).

---

## Human Verification Required

None required for automated correctness checks.

The following item requires a live data run to fully confirm, but is not a blocker for phase sign-off:

### 1. Cross-Source Duplicate Detection in Production Data

**Test:** After a full ingest run, query `find_duplicate_groups()` against the live database and inspect returned groups.
**Expected:** Records with the same grant opportunity_number from different sources (e.g., Grants.gov and SBIR) share a canonical_id and appear in the same duplicate group.
**Why human:** Requires live data and knowledge of specific cross-source grant numbers to validate the end-to-end result. The unit tests verify the algorithm; this validates the real data quality.

---

## Gaps Summary

One partial gap blocks full sign-off:

**QUAL-06 / Truth 4 — SBIR award amount validation not applied.** `validate_award_amounts` is imported in `grantflow/ingest/sbir.py` (line 21) but has zero call sites. SBIR awards and solicitations do not include `award_floor` or `award_ceiling` fields in their record dicts — the model columns are left NULL for all SBIR records. This means:

1. The unused import is dead code and should be cleaned up.
2. If SBIR API responses do carry budget range data (e.g., under different field names), that data is currently not being mapped to `award_floor`/`award_ceiling` and not validated.

The gap is low severity because SBIR data genuinely may not expose floor/ceiling ranges. The fix is either: (a) map any available SBIR budget fields to floor/ceiling and call validate_award_amounts, or (b) remove the unused import with a comment confirming SBIR has no floor/ceiling data.

All other must-haves are fully implemented, tested (137 tests passing), and wired correctly.

---

_Verified: 2026-03-24T19:30:00Z_
_Verifier: Claude (gsd-verifier)_
