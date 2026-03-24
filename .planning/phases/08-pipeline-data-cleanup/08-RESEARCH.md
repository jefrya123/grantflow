# Phase 8: Pipeline & Data Cleanup - Research

**Researched:** 2026-03-24
**Domain:** Python ingest pipeline, data normalization, dead code cleanup
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-02 | Full-text search uses PostgreSQL tsvector + GIN index (replacing FTS5) | FTS5 write path audit — verified no live FTS5 code remains in ingest files; audit finding appears resolved in prior phases |
| QUAL-01 | Eligibility codes normalized to human-readable categories | `normalize_eligibility_codes()` exists and is tested; sam_gov.py does not call it — wire required |
| QUAL-02 | Agency names/codes normalized across all sources | `normalize_agency_name()` exists and is tested; sam_gov.py does not call it — wire required |
| QUAL-05 | Date fields consistently ISO 8601 across all sources | `normalize_date()` exists and is tested; sam_gov.py uses private `_parse_sam_date()` which handles most formats but is redundant — normalizers.py already handles all those formats |
| QUAL-06 | Award amounts validated (floor <= ceiling, no negative values) | `validate_award_amounts` imported in sbir.py but never called; SBIR records have no floor/ceiling fields — remove dead import |
</phase_requirements>

---

## Summary

Phase 8 is a focused cleanup phase with three discrete changes across two files. All three gaps are independently actionable and carry zero schema migration risk — they are pure Python changes to existing ingest logic.

**Gap 1 — FTS5 remnants (FOUND-02):** The v1.0 audit flagged FTS5 write path code in grants_gov.py and run_all.py. Direct inspection of both files confirms no FTS5 references exist in the current codebase. This tech debt item appears to have been resolved during Phase 1 or 2 implementation. The planner should verify this during plan authoring by scanning for `fts5`, `FTS5`, and `INSERT INTO.*_fts` patterns, and treat this as a verification task rather than a removal task.

**Gap 2 — SAM.gov normalization (QUAL-01, QUAL-02, QUAL-05, QUAL-06):** `sam_gov.py` builds its `opp_data` dict directly from raw API fields without importing or calling any function from `normalizers.py`. The file has its own private `_parse_sam_date()` (23 lines) that handles the same formats `normalize_date()` handles. The fix is: import the four normalizer functions, call them on the appropriate fields inside the per-record loop, and optionally remove `_parse_sam_date()` since it becomes redundant. SAM.gov records have no `award_floor`/`award_ceiling` fields in the API response, so `validate_award_amounts` will be called with `(None, None)` — which is valid and returns `(None, None)` without side effects.

**Gap 3 — Dead import in sbir.py (QUAL-06):** `sbir.py` imports `validate_award_amounts` on line 21 but has zero call sites. SBIR records (both awards and solicitations) do not carry `award_floor` or `award_ceiling` fields. The Phase 4 verification doc explicitly diagnosed this: either wire the validator to floor/ceiling fields if they exist, or remove the import. Since neither `_ingest_awards()` nor `_ingest_solicitations()` populates those fields, the correct fix is removal with a clarifying comment.

**Primary recommendation:** One plan, three tasks: (1) verify/confirm FTS5 cleanup, (2) wire sam_gov.py through normalizers, (3) remove dead import from sbir.py. Add targeted tests for the SAM.gov normalization wiring.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| grantflow.normalizers | project | normalize_date, normalize_agency_name, normalize_eligibility_codes, validate_award_amounts | Established in Phase 4; all other ingestors use this module |
| pytest | project | Test runner | Project standard per global CLAUDE.md |

No new dependencies. This phase introduces zero new libraries.

**The normalizer API (confirmed from source):**
```python
from grantflow.normalizers import (
    normalize_date,
    normalize_eligibility_codes,
    normalize_agency_name,
    validate_award_amounts,
)
```

---

## Architecture Patterns

### Pattern 1: Normalizer call site — established pattern from grants_gov.py

All three sibling ingestors (grants_gov.py, sbir.py, usaspending.py) follow this pattern for building a record dict. SAM.gov should match exactly.

```python
# Source: grantflow/ingest/grants_gov.py lines 342-351 (XML path)
record["eligible_applicants"] = normalize_eligibility_codes(
    record.get("eligible_applicants")
)
record["agency_name"] = normalize_agency_name(record.get("agency_name"))
floor, ceiling = validate_award_amounts(
    record.get("award_floor"), record.get("award_ceiling")
)
record["award_floor"] = floor
record["award_ceiling"] = ceiling
```

### Pattern 2: SAM.gov opp_data dict (current, pre-fix)

The insertion point in sam_gov.py is after `opp_data` is fully built (around line 188) and before the upsert block. The normalizer calls go between building the dict and the `session.get()` call.

```python
# Current sam_gov.py lines 173-190 (the insertion window)
opp_data = {
    "id": opp_id,
    "source": "sam_gov",
    ...
    "agency_name": agency_name,           # ← normalize_agency_name() here
    "post_date": _parse_sam_date(...),    # ← replace with normalize_date()
    "close_date": _parse_sam_date(...),   # ← replace with normalize_date()
    ...
    "eligible_applicants": record.get("typeOfSetAside", ""),  # ← normalize_eligibility_codes() here
    ...
}
# Add after dict construction:
# opp_data["agency_name"] = normalize_agency_name(opp_data["agency_name"])
# opp_data["eligible_applicants"] = normalize_eligibility_codes(opp_data["eligible_applicants"])
# floor, ceiling = validate_award_amounts(opp_data.get("award_floor"), opp_data.get("award_ceiling"))
# opp_data["award_floor"] = floor
# opp_data["award_ceiling"] = ceiling
```

### Pattern 3: _parse_sam_date() vs normalize_date()

`_parse_sam_date()` in sam_gov.py handles:
- ISO 8601 with offset: `datetime.fromisoformat()` → `strftime("%Y-%m-%d")`
- Plain `YYYY-MM-DD`
- `MM/DD/YYYY`
- Falls back to raw value (lenient — this is a divergence from the standard)

`normalize_date()` in normalizers.py handles all those formats plus YYYYMMDD, MMDDYYYY, `Jan 15 2024`, `January 15 2024`, and ISO with time — and returns **None** on failure (strict, per Phase 4 decision). The normalizers.py function is a strict superset.

**Decision:** Replace `_parse_sam_date()` calls with `normalize_date()` and remove the private function. The only behavioral difference is that `normalize_date()` returns None on garbage input instead of the raw string — which is the correct behavior per the Phase 4 decision ("fail loudly rather than store garbage strings").

Note: `normalize_date()` does not include an `ISO 8601 with timezone offset` format in `_DATE_FORMATS`. The `_parse_sam_date()` handles this via `datetime.fromisoformat()`. Verify whether `normalize_date()` correctly handles `"2024-03-15T00:00:00-04:00"` — it includes `"%Y-%m-%dT%H:%M:%S"` but not the offset variant. **This is the one edge case to handle.** Either: (a) add ISO-with-offset to normalizers.py `_DATE_FORMATS`, or (b) pre-strip the offset before passing to `normalize_date()`. Option (a) is cleaner and makes the normalizer more complete.

### Anti-Patterns to Avoid
- **Parallel date parsing logic:** Do not leave `_parse_sam_date()` alongside `normalize_date()` calls — removes the point of having a shared normalizer
- **Silent fallback on bad dates:** `_parse_sam_date()` returns raw value on failure; `normalize_date()` returns None — do not change this behavior, None is correct
- **Calling validate_award_amounts and ignoring the result:** The return value must be unpacked and written back to the dict

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date parsing | New date parser in sam_gov.py | `normalize_date()` | Already handles all SAM.gov formats; `_parse_sam_date()` is a duplicate |
| Agency canonicalization | AGENCY_NAME_MAP in sam_gov.py | `normalize_agency_name()` | Map lives in normalizers.py; duplicating it creates drift risk |
| Eligibility code mapping | Inline dict in sam_gov.py | `normalize_eligibility_codes()` | 17-code map + JSON serialization already implemented and tested |
| Amount validation | Inline floor/ceiling check | `validate_award_amounts()` | Edge cases (negative, floor > ceiling, -0.0) already handled and tested |

---

## Common Pitfalls

### Pitfall 1: normalize_date() does not handle ISO 8601 with timezone offset
**What goes wrong:** SAM.gov dates arrive as `"2024-03-15T00:00:00-04:00"`. `normalize_date()` has `"%Y-%m-%dT%H:%M:%S"` but not `"%Y-%m-%dT%H:%M:%S%z"`. This format will return None after the fix if not handled.
**Why it happens:** `_DATE_FORMATS` tuple in normalizers.py (line 96-105) does not include a timezone-aware strptime format. `datetime.fromisoformat()` handles this natively but is not in the format loop.
**How to avoid:** Add `datetime.fromisoformat()` handling to `normalize_date()` as a pre-pass before the format loop, OR add `"%Y-%m-%dT%H:%M:%S%z"` to `_DATE_FORMATS`. The `fromisoformat()` approach is more robust.
**Warning signs:** Test `normalize_date("2024-03-15T00:00:00-04:00")` returns None after the fix — existing `test_parse_sam_date_iso_with_offset` in `tests/test_sam_gov.py` will catch this if updated to test `normalize_date` instead of `_parse_sam_date`.

### Pitfall 2: SAM.gov has no award_floor/award_ceiling in API response
**What goes wrong:** Calling `validate_award_amounts(None, None)` is safe (returns `(None, None)`), but the planner might skip the call entirely for SAM.gov since both values are always None. However, the correct approach is to include the call so the pattern is consistent and future-proof if SAM.gov ever adds these fields.
**How to avoid:** Include the `validate_award_amounts(None, None)` call in sam_gov.py — it's a no-op that documents the intent.

### Pitfall 3: FTS5 audit finding may already be resolved
**What goes wrong:** The planner writes a removal task for FTS5 code that no longer exists, wasting implementation effort and confusing the executor.
**Why it happens:** The v1.0 audit was written against a snapshot; subsequent phases may have cleaned this already.
**How to avoid:** Make the FTS5 task a verification task: "Grep for FTS5 patterns; if found, remove; document finding either way." The planner should not assume code exists just because the audit flagged it.

### Pitfall 4: Removing _parse_sam_date() breaks existing tests
**What goes wrong:** `tests/test_sam_gov.py` has 4 tests that directly call `_parse_sam_date()` (lines 18-43). Removing the function will break these tests.
**How to avoid:** Either: (a) update the tests to test `normalize_date()` instead (preferred — those tests now belong in test_normalizers.py or a new test section), or (b) keep `_parse_sam_date()` as a thin wrapper that calls `normalize_date()`. Option (a) is cleaner.

---

## Code Examples

### Normalizer import block (established pattern for all ingestors)
```python
# Source: grantflow/ingest/grants_gov.py lines 21-26
from grantflow.normalizers import (
    normalize_date,
    normalize_eligibility_codes,
    normalize_agency_name,
    validate_award_amounts,
)
```

### Removing dead import from sbir.py (current lines 17-21)
```python
# BEFORE (sbir.py lines 17-21):
from grantflow.normalizers import (
    normalize_date,
    normalize_eligibility_codes,
    normalize_agency_name,
)
# validate_award_amounts removed — SBIR records have no award_floor/award_ceiling fields

# AFTER: remove validate_award_amounts from the import block
# Add comment if desired:
# Note: validate_award_amounts not imported — SBIR award/solicitation records
# do not expose award_floor or award_ceiling fields.
```

### Proposed normalize_date() fix for ISO with offset
```python
# Source: grantflow/normalizers.py — proposed addition to normalize_date()
def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # Handle ISO 8601 with timezone offset (e.g. "2024-03-15T00:00:00-04:00")
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FTS5 virtual table for full-text search | PostgreSQL tsvector + GIN index | Phase 1 | Crash risk on PostgreSQL eliminated; FTS5 code should be fully gone |
| Per-ingestor date parsing (e.g. `_parse_sam_date`) | Shared `normalize_date()` | Phase 4 | Consistent behavior, single test surface |
| Raw eligibility codes stored as-is | `normalize_eligibility_codes()` mapping to human labels | Phase 4 | Human-readable API responses |

---

## Open Questions

1. **Does normalize_date() handle ISO 8601 with timezone offset?**
   - What we know: `_DATE_FORMATS` does not include `%z` format; `_parse_sam_date()` uses `datetime.fromisoformat()` which handles it natively
   - What's unclear: Whether `datetime.fromisoformat("2024-03-15T00:00:00-04:00")` succeeds in Python 3.13 (it does — Python 3.11+ supports offsets in fromisoformat)
   - Recommendation: Add `fromisoformat()` pre-pass to `normalize_date()` so the behavior is explicit and documented

2. **Are any FTS5 remnants actually present?**
   - What we know: grep of grantflow/ directory finds zero matches for fts5, FTS5, virtual table, or fts-related patterns
   - What's unclear: Whether the audit was against a different snapshot or earlier branch
   - Recommendation: Planner makes this a "verify then document" task — grep, confirm result, note in plan

3. **Should _parse_sam_date() be deleted or made a wrapper?**
   - What we know: 4 tests directly import and test it; removing it breaks those tests
   - Recommendation: Delete function, migrate the 4 test cases to test normalize_date() directly (the behavior they test is a subset of normalize_date's contract)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project standard) |
| Config file | pyproject.toml (inferred — no pytest.ini found) |
| Quick run command | `uv run pytest tests/test_sam_gov.py tests/test_normalizers.py -x` |
| Full suite command | `uv run pytest -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-02 | No FTS5 code in ingest files | smoke (grep assertion) | `uv run pytest tests/test_pipeline_cleanup.py::test_no_fts5_references -x` | ❌ Wave 0 |
| QUAL-01 | SAM.gov eligible_applicants normalized to human labels | unit | `uv run pytest tests/test_sam_gov.py::test_sam_gov_normalizes_eligibility -x` | ❌ Wave 0 |
| QUAL-02 | SAM.gov agency_name normalized via AGENCY_NAME_MAP | unit | `uv run pytest tests/test_sam_gov.py::test_sam_gov_normalizes_agency -x` | ❌ Wave 0 |
| QUAL-05 | SAM.gov dates arrive as ISO 8601 (normalize_date used) | unit | `uv run pytest tests/test_sam_gov.py -x` | ✅ (needs update) |
| QUAL-06 | validate_award_amounts not imported in sbir.py (dead code removed) | smoke (import check) | `uv run pytest tests/test_pipeline_cleanup.py::test_sbir_no_dead_import -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_sam_gov.py tests/test_normalizers.py -x`
- **Per wave merge:** `uv run pytest -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline_cleanup.py` — smoke tests for FOUND-02 (no FTS5) and QUAL-06 (no dead import); covers REQ FOUND-02, QUAL-06
- [ ] Update `tests/test_sam_gov.py` — migrate `_parse_sam_date` tests to `normalize_date`, add normalization wire tests (QUAL-01, QUAL-02, QUAL-05)

*(Existing `tests/test_normalizers.py` covers all normalizer functions thoroughly — no changes needed there)*

---

## Sources

### Primary (HIGH confidence)
- Direct file inspection: `grantflow/ingest/sam_gov.py` — confirmed no normalizer imports, has private `_parse_sam_date()`
- Direct file inspection: `grantflow/ingest/sbir.py` — confirmed `validate_award_amounts` imported at line 17-21, zero call sites in file
- Direct file inspection: `grantflow/normalizers.py` — confirmed all four normalizer functions present with tested behavior
- Direct file inspection: `grantflow/ingest/grants_gov.py` — confirmed normalizer call pattern to replicate
- Direct grep: zero FTS5/fts5 matches in `grantflow/` directory — audit finding appears resolved
- Direct file inspection: `tests/test_sam_gov.py` — confirmed 4 tests call `_parse_sam_date()` directly

### Secondary (MEDIUM confidence)
- `.planning/v1.0-MILESTONE-AUDIT.md` — authoritative gap list; FTS5 gap and SAM.gov normalization gap both documented
- `.planning/phases/04-data-quality/04-VERIFICATION.md` — detailed diagnosis of validate_award_amounts dead import in sbir.py

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all code directly inspected, no external research needed
- Architecture: HIGH — established patterns extracted directly from sibling ingestors
- Pitfalls: HIGH — timezone offset issue confirmed by reading `_DATE_FORMATS` tuple and `_parse_sam_date()` side by side; test breakage confirmed by reading test file

**Research date:** 2026-03-24
**Valid until:** Stable indefinitely — this is internal code, not external APIs
