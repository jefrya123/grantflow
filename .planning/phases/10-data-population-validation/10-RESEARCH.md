# Phase 10: Data Population & Validation - Research

**Researched:** 2026-03-24
**Domain:** Pipeline execution, data normalization, backfill migrations
**Confidence:** HIGH

## Summary

Phase 10 is an **execution and repair phase**, not a feature-building phase. All pipeline code exists from phases 1-9. The task is to run every pipeline, fix what breaks, backfill normalization on existing data, and add missing normalizer mappings for category codes and funding instrument codes that were never implemented.

The database currently holds 81,856 Grants.gov opportunities and 5,000 USAspending awards -- all other sources have zero records. SBIR ingestion failed (stuck at "running" with 0 records). SAM.gov was never attempted (no API key configured). State scrapers were never run (3 of 5 states require env-var dataset IDs that are unset). LLM enrichment was never run (no OPENAI_API_KEY). Critically, the existing Grants.gov data has raw codes for eligibility ("25"), category ("D"), and funding_instrument ("CA") that need backfill normalization.

**Primary recommendation:** Work in three waves: (1) add missing normalizer maps + backfill existing data, (2) configure and run all pipelines fixing failures, (3) run enrichment and validate API output end-to-end.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-03 | SBIR ingestion works reliably (fix rate limiting, retry logic) | SBIR ingestor exists but failed on first run; needs debugging (CSV download or API issue). Code at `grantflow/ingest/sbir.py` has retry logic already. |
| PIPE-04 | SAM.gov contract opportunities ingested (with registered API key, incremental design) | Code at `grantflow/ingest/sam_gov.py` is complete with incremental cursor. Needs SAM_GOV_API_KEY in .env. Public tier = 10 req/day limit. |
| STATE-02 | At least 5 state portals scraped and normalized into unified schema | 5 scrapers exist (CA, NY, IL, TX, CO). CA works without env vars. NY/IL/TX need dataset IDs. CO marked CONDITIONAL in legal review. |
| QUAL-01 | Eligibility codes normalized to human-readable categories | `normalize_eligibility_codes()` exists and works correctly. Problem: 81K existing records have bare codes ("25") not normalized JSON arrays. Need backfill. |
| QUAL-04 | LLM-powered categorization tags opportunities by topic/sector | `enrichment/tagger.py` and `enrichment/run_enrichment.py` exist. Uses instructor + gpt-4o-mini. Needs OPENAI_API_KEY. Batch size 500, concurrency 10. |
</phase_requirements>

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| httpx | >=0.27 | HTTP client for all pipeline fetches | Working |
| sqlalchemy | >=2.0 | ORM for all DB operations | Working |
| instructor | >=1.14.5 | Structured LLM output for topic tagging | Installed, untested |
| openai | >=2.29.0 | LLM provider for enrichment | Installed, needs API key |
| structlog | >=24.0 | Pipeline logging | Working |

### No New Dependencies Needed
This phase requires zero new libraries. All code is built; this is execution and data repair.

## Architecture Patterns

### Current Project Structure (relevant files)
```
grantflow/
  ingest/
    run_all.py          # Orchestrator: runs grants_gov, usaspending, sbir, sam_gov
    run_state.py         # Orchestrator: runs all 5 state scrapers
    grants_gov.py        # REST-first, XML-fallback. 81K records loaded.
    usaspending.py       # Working. 5K awards loaded.
    sbir.py              # FAILED. CSV download + solicitations API.
    sam_gov.py           # Never run. Needs SAM_GOV_API_KEY.
    state/
      base.py            # BaseStateScraper ABC
      california.py      # CKAN API (data.ca.gov) - no env vars needed
      new_york.py        # Socrata API - needs GRANTFLOW_NY_DATASET_ID
      illinois.py        # Socrata API - needs GRANTFLOW_IL_DATASET_ID
      texas.py           # needs GRANTFLOW_TX_DATASET_ID
      colorado.py        # CONDITIONAL legal status
  normalizers.py         # Has: eligibility, agency, date, award amounts
                         # Missing: category codes, funding instrument codes
  enrichment/
    tagger.py            # instructor + gpt-4o-mini topic classification
    run_enrichment.py    # CLI: `uv run python -m grantflow.enrichment.run_enrichment`
  database.py            # SQLite engine (not PostgreSQL despite Phase 1 migration code)
```

### Pattern: Backfill Migration for Existing Data
The existing 81K Grants.gov records have raw codes that need normalization. This is NOT an Alembic migration (it's a data transformation, not schema change). Use a standalone Python script that:
1. Queries records with raw eligibility/category/funding_instrument codes
2. Applies normalizers
3. Updates in batches of 500 with commits

### Pattern: Pipeline Execution Order
```
1. Add missing normalizer maps (category, funding_instrument)
2. Backfill existing Grants.gov data
3. Run SBIR ingestion (debug failure)
4. Configure and run SAM.gov ingestion
5. Configure and run state scrapers
6. Run LLM enrichment
7. Validate API output
```

### Anti-Patterns to Avoid
- **Do NOT re-run Grants.gov ingest to fix normalization** -- it takes a long time and re-downloads the XML. Backfill in-place instead.
- **Do NOT run all pipelines simultaneously** -- SQLite has write contention with WAL mode. Run sequentially.
- **Do NOT skip env var configuration** -- SAM.gov and 3 state scrapers will silently return 0 records without their env vars.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Category code mapping | Custom lookup | Module-level dict constant in normalizers.py | Matches existing ELIGIBILITY_CODE_MAP pattern |
| Funding instrument mapping | Custom lookup | Module-level dict constant in normalizers.py | Same pattern, same file |
| Data backfill | Alembic migration | Standalone script using SessionLocal | Not a schema change; Alembic data migrations are fragile |
| State dataset ID discovery | Manual search | Socrata API discovery endpoints | NY, IL, TX use Socrata; dataset IDs findable via their data portals |

## Common Pitfalls

### Pitfall 1: SBIR CSV Download Failure
**What goes wrong:** The SBIR awards CSV at `https://data.www.sbir.gov/awarddatapublic/award_data.csv` may be large (100MB+), time out, or return an error. The ingestion log shows status "running" with 0 records -- meaning it crashed before processing any rows.
**Why it happens:** Network timeout, CSV format changes, or the sbir.gov site being down.
**How to avoid:** Check if the CSV URL is still valid. Look at the actual error (the log entry has no error message, suggesting an unhandled exception before the finally block). Run `_download_csv()` in isolation first.
**Warning signs:** `status='running'` in ingestion_log with no `completed_at` and no `error` -- means the process crashed without hitting the except/finally blocks.

### Pitfall 2: Eligibility Data Already Has Bare Codes
**What goes wrong:** The normalizer `normalize_eligibility_codes("25")` correctly produces `'["Others (see agency eligibility text)"]'`, but 81K existing records store bare "25" because they were ingested before normalization was wired in (or the XML parser stored the raw value).
**Why it happens:** The XML `_parse_element` function does call `normalize_eligibility_codes`, but examining the actual stored data shows bare codes. This means either: (a) the initial bulk ingest predated the normalizer, or (b) the XML data provides codes in a format the normalizer didn't handle at the time.
**How to avoid:** Run a backfill script that re-normalizes all eligibility values. Also verify that NEW ingests produce normalized values.

### Pitfall 3: No Category or Funding Instrument Normalizers Exist
**What goes wrong:** Categories show as "D", "M", "C", "O", "E" and funding instruments as "CA", "G", "O", "PC". There are NO normalizer functions for these in normalizers.py.
**Why it happens:** Phase 4 (Data Quality) built eligibility and agency normalizers but did not build category or funding instrument normalizers. The success criteria for this phase require human-readable labels.
**How to avoid:** Add `CATEGORY_CODE_MAP` and `FUNDING_INSTRUMENT_MAP` dicts to normalizers.py, add `normalize_category()` and `normalize_funding_instrument()` functions, wire them into the ingestors, and backfill existing data.

### Pitfall 4: SAM.gov API Key Not Configured
**What goes wrong:** `ingest_sam_gov()` checks `if not SAM_GOV_API_KEY` and returns `status="skipped"` silently.
**Why it happens:** .env has no SAM_GOV_API_KEY entry. The public tier allows 10 requests/day.
**How to avoid:** Register at SAM.gov for an API key (https://api.sam.gov). Add to .env. Even with public tier, the ingestion code handles 429 rate limits and saves partial results.

### Pitfall 5: State Scraper Env Vars Missing
**What goes wrong:** NY, IL, TX scrapers return empty lists when their dataset IDs are not set. Only CA (hardcoded DATASET_ID) and CO work without env vars.
**Why it happens:** Per Phase 5 decision: "NY/IL/TX dataset IDs require PoC discovery -- env-var gated with graceful empty-list skip"
**How to avoid:** Discover the correct Socrata dataset IDs for each state's grant data portal and add them to .env. STATE-02 requires at least 5 states, so all 5 need to work.

### Pitfall 6: SQLite Write Contention
**What goes wrong:** Running multiple ingestors concurrently on SQLite causes "database is locked" errors.
**Why it happens:** Despite WAL mode and busy_timeout=5000ms, heavy write batches can still block.
**How to avoid:** Run pipelines strictly sequentially (which run_all.py already does). Never run state ingestion in parallel with federal ingestion.

### Pitfall 7: LLM Enrichment Cost
**What goes wrong:** Enriching 81K+ opportunities at gpt-4o-mini pricing can be expensive.
**Why it happens:** Default batch size is 500, but total un-tagged records will be 80K+.
**How to avoid:** Use ENRICHMENT_BATCH_SIZE env var to limit to a meaningful sample (e.g., 500-1000) for initial validation. The success criterion says "meaningful sample", not 100% coverage.

## Code Examples

### Grants.gov Category Code Mapping (needs to be added)
```python
# Source: Grants.gov XML Schema Documentation
# https://www.grants.gov/xml-extract
CATEGORY_CODE_MAP: dict[str, str] = {
    "D": "Discretionary",
    "M": "Mandatory",
    "C": "Continuation",
    "E": "Earmark",
    "O": "Other",
}
```

### Grants.gov Funding Instrument Mapping (needs to be added)
```python
# Source: Grants.gov XML Schema Documentation
FUNDING_INSTRUMENT_MAP: dict[str, str] = {
    "G": "Grant",
    "CA": "Cooperative Agreement",
    "PC": "Procurement Contract",
    "O": "Other",
}
```

### Backfill Pattern for Existing Data
```python
from grantflow.database import SessionLocal
from grantflow.models import Opportunity
from grantflow.normalizers import normalize_eligibility_codes, normalize_category, normalize_funding_instrument

def backfill_normalization():
    session = SessionLocal()
    batch_size = 500
    offset = 0
    updated = 0

    while True:
        rows = session.query(Opportunity).offset(offset).limit(batch_size).all()
        if not rows:
            break
        for opp in rows:
            changed = False
            # Eligibility: re-normalize bare codes
            if opp.eligible_applicants and not opp.eligible_applicants.startswith("["):
                opp.eligible_applicants = normalize_eligibility_codes(opp.eligible_applicants)
                changed = True
            # Category: normalize code to label
            if opp.category and len(opp.category) <= 2:
                opp.category = normalize_category(opp.category)
                changed = True
            # Funding instrument: normalize code to label
            if opp.funding_instrument and len(opp.funding_instrument) <= 2:
                opp.funding_instrument = normalize_funding_instrument(opp.funding_instrument)
                changed = True
            if changed:
                updated += 1
        session.commit()
        offset += batch_size
    session.close()
    return updated
```

### Running Individual Pipelines for Debugging
```bash
# Run SBIR alone to debug failure
uv run python -c "from grantflow.ingest.sbir import ingest_sbir; print(ingest_sbir())"

# Run SAM.gov alone (after setting API key)
uv run python -c "from grantflow.ingest.sam_gov import ingest_sam_gov; print(ingest_sam_gov())"

# Run state scrapers alone
uv run python -m grantflow.ingest.run_state

# Run enrichment alone
uv run python -m grantflow.enrichment.run_enrichment

# Run full federal pipeline
uv run python -m grantflow.ingest.run_all
```

## State of the Art

| Old State | Current State | Impact |
|-----------|---------------|--------|
| 81K Grants.gov only | Need multi-source data | SBIR, SAM.gov, 5 states must have records |
| Raw eligibility codes ("25") | Must be human-readable JSON arrays | Backfill + normalizer wiring |
| Raw category codes ("D") | Must be human-readable ("Discretionary") | New normalizer + backfill |
| Raw funding_instrument ("CA") | Must be human-readable ("Cooperative Agreement") | New normalizer + backfill |
| topic_tags 0% populated | Meaningful sample must have tags | Run enrichment with OPENAI_API_KEY |
| SBIR status="running" 0 records | Must complete successfully | Debug and fix failure |
| SAM.gov never attempted | Must have contract opportunities | Configure API key and run |
| State scrapers never run | 5 states with data in unified schema | Configure env vars and run |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-03 | SBIR ingestion completes with >0 records | smoke/integration | `uv run python -c "from grantflow.ingest.sbir import ingest_sbir; r=ingest_sbir(); assert r['status']=='success' and r['records_processed']>0"` | N/A (live test) |
| PIPE-04 | SAM.gov ingestion completes with records | smoke/integration | `uv run python -c "from grantflow.ingest.sam_gov import ingest_sam_gov; r=ingest_sam_gov(); assert r['status'] in ('success','partial') and r['records_processed']>0"` | N/A (live test) |
| STATE-02 | 5 state scrapers produce data | smoke/integration | `uv run python -c "from grantflow.database import SessionLocal; from sqlalchemy import text; s=SessionLocal(); r=s.execute(text(\"SELECT source, COUNT(*) FROM opportunities WHERE source LIKE 'state_%' GROUP BY source\")).fetchall(); print(r); assert len(r)>=5"` | N/A (live test) |
| QUAL-01 | Eligibility shows human-readable labels | unit | `uv run pytest tests/test_normalizers.py -x -q` | Yes |
| QUAL-04 | topic_tags populated on sample | smoke | `uv run python -c "from grantflow.database import SessionLocal; from sqlalchemy import text; s=SessionLocal(); c=s.execute(text(\"SELECT COUNT(*) FROM opportunities WHERE topic_tags IS NOT NULL\")).scalar(); print(c); assert c>0"` | N/A (live test) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green + live data validation queries pass

### Wave 0 Gaps
- [ ] `tests/test_normalizers.py` -- needs tests for new `normalize_category()` and `normalize_funding_instrument()` functions
- [ ] No existing integration test for backfill script -- verify via DB query after execution
- [ ] Live pipeline tests cannot run in CI (need network + API keys) -- manual verification

## Open Questions

1. **SBIR Failure Root Cause**
   - What we know: ingestion_log shows status="running", 0 records, no error, no completed_at. This means the process crashed before reaching the finally block.
   - What's unclear: Was it a download timeout? CSV format change? Python crash?
   - Recommendation: Run `_download_csv()` in isolation, then `_ingest_awards()` separately to find the exact failure point.

2. **State Dataset IDs for NY/IL/TX**
   - What we know: These use Socrata API and need GRANTFLOW_NY_DATASET_ID, GRANTFLOW_IL_DATASET_ID, GRANTFLOW_TX_DATASET_ID env vars.
   - What's unclear: What are the correct dataset IDs? They require discovery via state data portal websites.
   - Recommendation: Search each state's open data portal for grant-related datasets and set the env vars.

3. **SAM.gov API Key Registration**
   - What we know: No key configured. Public tier = 10 requests/day. Code handles this with MAX_PAGES=50 and rate limit detection.
   - What's unclear: Whether user has already registered or needs to. Registration may take time for approval.
   - Recommendation: Register at https://api.sam.gov if not already done. Even public tier (no key) allows some access -- test with empty key first to see if the endpoint works without authentication.

4. **Colorado Legal Status**
   - What we know: Marked CONDITIONAL in LEGAL_REVIEW.md. No centralized open data mandate.
   - What's unclear: Whether scraping is actually safe.
   - Recommendation: Review robots.txt and ToS before running. If blocked, STATE-02 still needs 5 states -- would need to find an alternative or confirm Colorado is safe.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: all ingestor files, normalizers.py, models.py, config.py
- Live database queries: confirmed exact state of all data (81K grants_gov, 5K usaspending awards, 0 SBIR, 0 SAM.gov, 0 state)
- Live normalizer testing: confirmed `normalize_eligibility_codes("25")` produces correct output

### Secondary (MEDIUM confidence)
- Grants.gov category codes (D/M/C/E/O) and funding instrument codes (G/CA/PC/O) -- based on standard Grants.gov XML schema documentation. These are well-known standard codes.

### Tertiary (LOW confidence)
- State portal dataset IDs for NY/IL/TX -- need discovery. The Socrata API pattern is correct but specific dataset IDs are unknown.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all code exists and is inspected
- Architecture: HIGH - this is execution of existing code, not new architecture
- Pitfalls: HIGH - all identified from live database state and code inspection
- Normalization gaps: HIGH - confirmed via DB queries showing raw codes
- State scraper readiness: MEDIUM - code exists but env vars need discovery

**Research date:** 2026-03-24
**Valid until:** 2026-04-07 (30 days -- code is stable, external APIs may change)
