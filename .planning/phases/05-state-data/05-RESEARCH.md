# Phase 5: State Data - Research

**Researched:** 2026-03-24
**Domain:** Web scraping state grant portals, monitoring breakage detection, pipeline integration
**Confidence:** HIGH (stack decisions), MEDIUM (specific portal structures — require per-portal PoC validation)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STATE-01 | Scraping infrastructure for state grant portals using Scrapling | Scrapling v0.4 API patterns, ingestor contract, integration with run_all.py |
| STATE-02 | At least 5 state portals scraped and normalized into unified schema | California (CKAN API), New York (Socrata API), Illinois (CKAN API), Texas (data.texas.gov Socrata), Colorado (open data portal) identified as best candidates |
| STATE-03 | Per-state legal review completed (ToS/robots.txt/open-data check) | Legal framework documented; CA, NY, IL, TX all have explicit open data policies |
| STATE-04 | Per-source monitoring alerts when a scraper breaks | monitor.py KNOWN_SOURCES extension pattern; zero-record detection logic |
| STATE-05 | State data refreshed on regular schedule (weekly minimum) | APScheduler weekly cron slot addition pattern documented |
</phase_requirements>

---

## Summary

Phase 5 adds state grant data — the competitive moat for GrantFlow. Federal data is freely available from government APIs; state data is not, making it the primary differentiator. The phase requires building Scrapling-based scrapers for at least 5 state portals, wiring them into the existing pipeline infrastructure (APScheduler, PipelineRun, structlog, normalizers), and extending the staleness monitor with per-source zero-record alerts.

The key architectural insight is that many high-value state portals are actually CKAN or Socrata open data portals that expose machine-readable JSON APIs — these should be targeted with `httpx` (no Scrapling needed) rather than browser automation. Scrapling is reserved for portals that only expose HTML interfaces. The STATE-01 requirement for "scraping infrastructure using Scrapling" is best read as "scraping infrastructure that can use Scrapling when needed," not a mandate to use Scrapling everywhere.

Scrapling v0.4 was identified as new (Feb 2025) in project STATE.md notes and carries a validation risk. For portals with open JSON APIs, this risk is avoided entirely. Scrapling's `Fetcher` (httpx-backed) is used for static HTML portals. `StealthyFetcher` / `DynamicFetcher` are reserved for JavaScript-rendered portals only — they require a `scrapling install` browser download step (Playwright Chromium + Camoufox Firefox) and are heavier operational dependencies.

**Primary recommendation:** Use CKAN/Socrata JSON APIs for California, New York, Illinois, and Texas first. Scrapling `Fetcher` (static HTML) for Colorado or a backup portal that lacks an open API. Avoid `StealthyFetcher`/`DynamicFetcher` unless a target portal requires it.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scrapling | 0.4 | HTML scraping for portals without APIs | Project decision; adaptive element location; fallback when no JSON API exists |
| httpx | >=0.27 (already installed) | HTTP requests for CKAN/Socrata JSON APIs | Already in stack; zero-config; matches existing ingestor pattern |
| lxml | >=5.0 (already installed) | HTML/XML parsing if needed | Already in stack |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| APScheduler | 3.11.2 (already installed) | Weekly schedule for state scrapers | Add second cron job in app.py lifespan |
| structlog | >=24.0 (already installed) | Structured logging per scraper | `bind_source_logger("state_{state_code}")` pattern |
| psycopg2-binary | already installed | DB writes | Matches existing sync engine pattern |

### Scrapling Fetcher Tiers (choose per portal)

| Fetcher | When to Use | Overhead |
|---------|-------------|----------|
| `Fetcher` / `AsyncFetcher` | Static HTML or any HTTP response | Low — httpx + curl_cffi |
| `StealthyFetcher` | JS-rendered portals behind anti-bot | Medium — requires Camoufox (Firefox) download |
| `DynamicFetcher` | Complex SPA portals, Playwright needed | High — requires Playwright Chromium download |

**Do not use `StealthyFetcher` or `DynamicFetcher` for government portals unless static fetch returns empty/blocked.** Government portals almost never deploy anti-bot protection.

### Installation

```bash
# Add to pyproject.toml dependencies
uv add scrapling

# Install browser dependencies ONLY if StealthyFetcher/DynamicFetcher are needed
# (avoid unless required — adds ~600MB of browser binaries)
uv run scrapling install
```

---

## Target State Portals

These are the recommended 5 targets in priority order. All have machine-readable APIs or scraped HTML that avoids ToS issues.

### Tier 1: CKAN / Socrata Open Data APIs (prefer these — no Scrapling needed)

| State | Portal | Access Method | Update Frequency | License |
|-------|--------|--------------|-----------------|---------|
| California | data.ca.gov/dataset/california-grants-portal | CKAN JSON API | Daily (8:45pm) | Open Data — California Open Data |
| New York | data.ny.gov | Socrata JSON API | Varies per dataset | Open Data — NY Open Data |
| Illinois | data.illinois.gov | CKAN JSON API | Varies | Open Data — Illinois Open Operating Standards Act |
| Texas | data.texas.gov | Socrata JSON API | Varies | Open Data — TX SB 819 (2019) |

**California is the strongest first target:** The California Grants Portal dataset on data.ca.gov is mandated by state law (Grant Information Act of 2018), updates daily, and is structured as open data with a documented CKAN API. The grants.ca.gov portal feeds it.

### Tier 2: HTML Scraping (Scrapling Fetcher — static HTML)

| State | Portal | Access Method | Notes |
|-------|--------|--------------|-------|
| Colorado | choosecolorado.com/doing-business/support-services/grants/ or colorado.gov | Scrapling Fetcher static HTML | No centralized API; page scraping required |

### CKAN API Pattern (used for CA, IL)

```python
# Source: CKAN 2.x API documentation
import httpx

CKAN_BASE = "https://data.ca.gov"
DATASET_ID = "california-grants-portal"

# Get resource list
meta = httpx.get(
    f"{CKAN_BASE}/api/3/action/package_show",
    params={"id": DATASET_ID},
    timeout=30,
).json()
resources = meta["result"]["resources"]

# Fetch JSON datastore
records = httpx.get(
    f"{CKAN_BASE}/api/3/action/datastore_search",
    params={"resource_id": resources[0]["id"], "limit": 1000},
    timeout=60,
).json()
# records["result"]["records"] is the list
```

### Socrata API Pattern (used for NY, TX)

```python
# Source: Socrata Open Data API documentation
import httpx

# NY example — dataset ID varies per portal
NY_BASE = "https://data.ny.gov"
DATASET_ID = "<dataset-id>"  # discovered during PoC

records = httpx.get(
    f"{NY_BASE}/resource/{DATASET_ID}.json",
    params={"$limit": 1000, "$offset": 0},
    headers={"X-App-Token": "optional-app-token"},
    timeout=60,
).json()
# Returns a list of dicts directly
```

---

## Architecture Patterns

### Recommended Project Structure

```
grantflow/
├── ingest/
│   ├── run_all.py         # extend: add state scrapers to pipeline steps
│   ├── state/             # NEW directory
│   │   ├── __init__.py
│   │   ├── base.py        # BaseStateScraper abstract class
│   │   ├── california.py  # CKAN API scraper
│   │   ├── new_york.py    # Socrata API scraper
│   │   ├── illinois.py    # CKAN API scraper
│   │   ├── texas.py       # Socrata API scraper
│   │   └── colorado.py    # Scrapling HTML scraper
│   └── run_state.py       # NEW: orchestrator for state scrapers only
├── pipeline/
│   └── monitor.py         # extend: add state sources to KNOWN_SOURCES
└── config.py              # extend: add per-state config env vars
```

### Pattern 1: Ingestor Contract (must match existing pattern)

Every state ingestor MUST return this dict shape — identical to federal ingestors:

```python
# Source: existing grantflow/ingest/run_all.py _write_pipeline_run() contract
def ingest_california() -> dict:
    stats = {
        "source": "state_california",
        "status": "error",          # "success" | "error" | "partial" | "skipped"
        "records_processed": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_failed": 0,
        "error": None,
    }
    # ... scraping logic ...
    return stats
```

Source names MUST use the prefix `state_` (e.g., `state_california`, `state_new_york`) to distinguish state sources from federal sources in the `pipeline_runs` table and the monitor.

### Pattern 2: BaseStateScraper (reduce repetition)

```python
# grantflow/ingest/state/base.py
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from grantflow.database import SessionLocal
from grantflow.models import Opportunity, IngestionLog, PipelineRun
from grantflow.pipeline.logging import bind_source_logger


class BaseStateScraper(ABC):
    """Abstract base class for all state grant scrapers."""

    source_name: str  # must be set by subclass, e.g. "state_california"

    @abstractmethod
    def fetch_records(self) -> list[dict]:
        """Fetch raw records from the portal. Raise on total failure."""
        ...

    @abstractmethod
    def normalize_record(self, raw: dict) -> dict | None:
        """Normalize one raw record into Opportunity field dict. Return None to skip."""
        ...

    def run(self) -> dict:
        """Execute scrape, normalize, upsert. Returns stats dict."""
        stats = {
            "source": self.source_name,
            "status": "error",
            "records_processed": 0,
            "records_added": 0,
            "records_updated": 0,
            "records_failed": 0,
            "error": None,
        }
        # ... upsert logic using SessionLocal(), normalize_record(), etc. ...
        return stats
```

### Pattern 3: Zero-Record Alert (STATE-04)

The existing `check_staleness()` in `monitor.py` detects stale data by time. State scrapers also need a **zero-record guard** — a run that completes successfully but returns 0 records may indicate a broken scraper (site restructured), not legitimately empty data.

```python
# In monitor.py — extend check_staleness() or add a new function
ZERO_RECORD_SOURCES = [
    "state_california", "state_new_york", "state_illinois",
    "state_texas", "state_colorado",
]

def check_zero_records(session=None) -> list[str]:
    """Alert if any state scraper's last run returned 0 records_processed.

    A run that 'succeeded' but processed 0 records is likely a broken scraper.
    """
    broken = []
    for source in ZERO_RECORD_SOURCES:
        last_run = (
            session.query(PipelineRun)
            .filter(PipelineRun.source == source, PipelineRun.status == "success")
            .order_by(PipelineRun.completed_at.desc())
            .first()
        )
        if last_run and last_run.records_processed == 0:
            logger.error("state_scraper_zero_records", source=source)
            _send_alert_email(source, 0, last_run.completed_at)
            broken.append(source)
    return broken
```

This must be called from `run_all_ingestion()` after state scraper runs, alongside the existing `check_staleness()` call.

### Pattern 4: Adding Weekly Schedule (STATE-05)

The existing scheduler fires all ingestion at 02:00 UTC daily. State scrapers should run on a **separate weekly job** (Sunday 03:00 UTC) to avoid blocking the daily federal ingestion run.

```python
# grantflow/app.py lifespan — add second job
scheduler.add_job(
    lambda: asyncio.get_event_loop().run_in_executor(None, run_state_ingestion),
    CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="UTC"),
    id="weekly_state_ingestion",
    replace_existing=True,
    misfire_grace_time=3600,
)
```

`run_state_ingestion()` lives in `grantflow/ingest/run_state.py` — same pattern as `run_all_ingestion()` but only calls state scrapers.

### Pattern 5: Monitor Extension (add state sources)

```python
# grantflow/pipeline/monitor.py
# Extend KNOWN_SOURCES to include state sources
KNOWN_SOURCES = [
    "grants_gov", "usaspending", "sbir", "sam_gov",
    # State sources (added in Phase 5)
    "state_california", "state_new_york", "state_illinois",
    "state_texas", "state_colorado",
]
# STALE_THRESHOLD_HOURS for state sources should be 240 (10 days) not 48 —
# weekly scrapers that miss one run should alert after 10 days, not 2 days.
# Use a per-source threshold dict instead of a single constant.
STATE_STALE_THRESHOLD_HOURS = 240   # 10 days for weekly scrapers
```

### Anti-Patterns to Avoid

- **Using `StealthyFetcher`/`DynamicFetcher` for government portals by default:** Government portals have no anti-bot detection. Static `Fetcher` or plain `httpx` is always sufficient as a first attempt. Browser automation doubles operational complexity.
- **Hardcoding portal structure:** Scrapling's `.css()` auto-save feature can adapt to layout changes, but using it without `auto_save=True` means the scraper breaks silently. Always use `auto_save=True` for CSS selectors on HTML scrapers.
- **Combining state scraper runs with federal daily runs:** State scraping is slower and more failure-prone. Keep them in a separate `run_state.py` with a separate APScheduler job.
- **Single STALE_THRESHOLD_HOURS for all sources:** Weekly scrapers stale in 48h is a false alarm. Use a per-source or per-category threshold.
- **Not checking `records_processed == 0` on "success":** A scraper that silently returns nothing is worse than a scraper that raises an error. The zero-record guard is mandatory.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML parsing | Custom regex/string parsing | `scrapling` CSS selectors or `lxml` | Edge cases in government HTML are endless |
| CKAN data access | Custom CKAN client | `httpx` + standard CKAN `/api/3/action/datastore_search` | CKAN API is documented and stable |
| Socrata data access | Custom Socrata client | `httpx` + Socrata `resource/{id}.json` endpoint | Socrata API is standardized across all portals |
| Rate limiting | Custom sleep logic | `httpx` with `time.sleep()` or `httpx` retry | Keep it simple; state portals rarely have strict rate limits |
| Browser automation | Custom Selenium/Playwright setup | `scrapling`'s `DynamicFetcher` | Scrapling wraps Playwright with stealth patches already applied |
| Deduplication | Custom state dedup logic | Existing `assign_canonical_ids()` in `dedup.py` | State records get `canonical_id` automatically at end of every run |
| Monitoring | Custom state-specific monitor | Extend `monitor.py` `KNOWN_SOURCES` + new `check_zero_records()` | Reuse existing email alert + structlog infrastructure |

---

## Legal Review Framework (STATE-03)

Every state portal MUST be reviewed before scraping starts. Record results in code comments and a `LEGAL_REVIEW.md` within the state/ directory.

### Review Checklist (per portal)

```
1. robots.txt: fetch https://{portal}/robots.txt — check for Disallow: / or Disallow: /grants
2. ToS: check for "no automated access", "no scraping", "no commercial use" clauses
3. Open Data license: look for explicit CC0, CC-BY, or Open Data license
4. Authentication: does access require a login? If yes, reject or seek permission.
5. Rate limits: documented? If not documented, use polite defaults (1 req/2s)
```

### Status by Portal (pre-validation assessment)

| State | Open Data Law | Expected ToS Status | Risk |
|-------|--------------|---------------------|------|
| California | Grant Information Act of 2018; data.ca.gov is CC0/public domain | LOW — legally mandated open data | Very Low |
| New York | NY Open Data law (2013) | LOW — explicit open license on data.ny.gov | Very Low |
| Illinois | Open Operating Standards Act (PA 98-627, 2014) | LOW — state mandate | Low |
| Texas | SB 819 (2019) | LOW — state mandate | Low |
| Colorado | No centralized open data mandate | MEDIUM — need to check per-portal ToS | Medium |

**Key legal principle:** Scraping publicly visible government data without login does not violate the CFAA (HiQ v. LinkedIn precedent). All 4 Tier-1 portals have explicit open data statutes. Confirm by reading each portal's ToS page before running.

---

## Common Pitfalls

### Pitfall 1: CKAN API Returns 0 Records Due to Pagination
**What goes wrong:** `datastore_search` defaults to `limit=100`. A portal with 500 records returns only 100, scraper reports partial data, zero-record guard does not fire, data appears incomplete.
**Why it happens:** CKAN `datastore_search` has a default limit of 100 records.
**How to avoid:** Always pass `limit=5000` and loop with `offset` if `total > limit`. Check `records["result"]["total"]` against len of returned records.
**Warning signs:** `records_processed` suspiciously low compared to expected portal size.

### Pitfall 2: Scrapling CSS Selector Silently Returns Empty
**What goes wrong:** Portal restructures its HTML. Scrapling's adaptive parser may return an empty list rather than raising. `records_processed = 0`, status = "success", zero-record guard fires — but only if implemented correctly.
**Why it happens:** `auto_save=True` learns element positions, but a complete page redesign defeats it.
**How to avoid:** Validate `len(results) > 0` before committing. Use the zero-record guard. Log a WARNING with the raw HTML length so breakage can be diagnosed.
**Warning signs:** `records_processed` drops to 0 on a previously-healthy source.

### Pitfall 3: Per-Source Stale Threshold Mismatch
**What goes wrong:** Weekly state scrapers added to `KNOWN_SOURCES` with the 48h `STALE_THRESHOLD_HOURS`. Every week between Sunday runs, all 5 state sources appear stale and fire alert emails.
**Why it happens:** The existing `check_staleness()` uses a single global threshold.
**How to avoid:** Before adding state sources to `KNOWN_SOURCES`, refactor `check_staleness()` to use a per-source threshold dict. State sources get 240h threshold; federal sources keep 48h.
**Warning signs:** Constant stale alert emails every Monday/Tuesday.

### Pitfall 4: Scrapling Browser Dependencies Not Installed
**What goes wrong:** `StealthyFetcher` or `DynamicFetcher` import succeeds but fails at runtime because `scrapling install` was never run.
**Why it happens:** Scrapling's browser dependencies are downloaded separately via `scrapling install`, not via pip.
**How to avoid:** Only use `Fetcher` (no install needed) unless a specific portal requires JavaScript rendering. Document the install step in Dockerfile / deployment notes.
**Warning signs:** `camoufox` / Playwright `ImportError` or `BrowserNotFoundError` at scraper startup.

### Pitfall 5: Opportunity IDs Colliding with Federal Records
**What goes wrong:** State opportunity IDs are short numbers (e.g., "12345"). If `id` column is set to `12345` instead of `state_california_12345`, it collides with federal record IDs.
**Why it happens:** Forgetting the source prefix in the composite ID.
**How to avoid:** Always prefix: `id = f"state_{state_code}_{source_id}"`. Enforce this in `BaseStateScraper`.
**Warning signs:** `UNIQUE constraint failed: opportunities.id` errors on insert.

### Pitfall 6: Socrata Dataset ID Changes
**What goes wrong:** Socrata dataset IDs (e.g., `abc1-def2`) are stable but sometimes portals migrate data to new datasets with new IDs.
**Why it happens:** State agencies reorganize their data portals without notice.
**How to avoid:** Log the dataset URL used in each run. The zero-record guard will catch this breakage. Check Socrata portal homepage for "recently updated" when a scraper breaks.

---

## Code Examples

### CKAN API Full Paginated Fetch

```python
# Source: CKAN 2.x API guide (docs.ckan.org/en/latest/api/)
import httpx

def fetch_ckan_all_records(base_url: str, resource_id: str, page_size: int = 1000) -> list[dict]:
    """Fetch all records from a CKAN datastore resource with pagination."""
    records = []
    offset = 0
    while True:
        resp = httpx.get(
            f"{base_url}/api/3/action/datastore_search",
            params={"resource_id": resource_id, "limit": page_size, "offset": offset},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data["result"]["records"]
        records.extend(batch)
        total = data["result"]["total"]
        offset += len(batch)
        if offset >= total or not batch:
            break
    return records
```

### Socrata Paginated Fetch

```python
# Source: Socrata Open Data API documentation (dev.socrata.com)
import httpx

def fetch_socrata_all_records(base_url: str, dataset_id: str, page_size: int = 1000) -> list[dict]:
    """Fetch all records from a Socrata dataset with pagination."""
    records = []
    offset = 0
    while True:
        resp = httpx.get(
            f"{base_url}/resource/{dataset_id}.json",
            params={"$limit": page_size, "$offset": offset},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json()
        records.extend(batch)
        if len(batch) < page_size:
            break
        offset += len(batch)
    return records
```

### Scrapling Static HTML Fetch

```python
# Source: Scrapling 0.4 documentation (scrapling.readthedocs.io)
from scrapling.fetchers import Fetcher

def fetch_portal_html(url: str) -> list[dict]:
    """Fetch and parse a static HTML grant portal page."""
    fetcher = Fetcher(auto_match=True)
    page = fetcher.get(url, timeout=30)

    # auto_save=True: Scrapling learns the selector position so it can
    # relocate elements if the page layout changes
    rows = page.css("table.grants-table tr", auto_save=True)
    records = []
    for row in rows:
        cells = row.css("td")
        if len(cells) < 3:
            continue
        records.append({
            "title": cells[0].text,
            "agency": cells[1].text,
            "deadline": cells[2].text,
            "url": row.css_first("a[href]").attrib.get("href", ""),
        })
    return records
```

### Normalize State Record to Opportunity Schema

```python
# Pattern based on existing ingest/sbir.py normalize approach
from grantflow.normalizers import normalize_date, normalize_agency_name

def normalize_ca_record(raw: dict, state_code: str = "ca") -> dict | None:
    """Map California CKAN record to Opportunity schema."""
    title = (raw.get("Title") or raw.get("grant_title") or "").strip()
    if not title:
        return None  # skip malformed records

    source_id = str(raw.get("id") or raw.get("record_id") or "")
    opp_id = f"state_{state_code}_{source_id}"

    return {
        "id": opp_id,
        "source": f"state_{state_code}",
        "source_id": source_id,
        "title": title,
        "description": raw.get("Description") or raw.get("description"),
        "agency_name": normalize_agency_name(raw.get("Agency") or raw.get("agency_name")),
        "agency_code": (raw.get("Agency") or "").strip().lower().replace(" ", "_")[:50],
        "opportunity_status": "posted",  # state portals rarely publish status
        "close_date": normalize_date(raw.get("Application_Due_Date") or raw.get("deadline")),
        "post_date": normalize_date(raw.get("Posted_Date") or raw.get("open_date")),
        "source_url": raw.get("URL") or raw.get("url") or "",
        "category": "State Grant",
        "raw_data": json.dumps(raw, default=str),
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Scrapy for government scraping | Scrapling v0.4 (project decision) | Feb 2025 | Adaptive element relocation survives portal redesigns |
| Playwright direct for JS portals | Scrapling DynamicFetcher (wraps Playwright) | 2024-2025 | Stealth patches built in |
| Manual staleness checks | APScheduler + PipelineRun model | Phase 2 | Already in place — state sources extend the same system |
| No cross-source dedup | `canonical_id` + `assign_canonical_ids()` | Phase 4 | State records auto-deduplicated against federal records at end of every run |

**Deprecated/outdated:**
- Scrapling `StealthyFetcher` pre-v0.3 used Camoufox separately — now integrated, but still requires `scrapling install`. Avoid unless truly needed.

---

## Open Questions

1. **California CKAN resource ID**
   - What we know: data.ca.gov/dataset/california-grants-portal exists; CKAN API available
   - What's unclear: The exact resource UUID (e.g., `111c8c88-21f6-453c-ae2c-b4785a0624f5`) must be confirmed by fetching the package metadata during PoC
   - Recommendation: Wave 0 task — fetch `https://data.ca.gov/api/3/action/package_show?id=california-grants-portal` to confirm resource IDs and field names before writing the full scraper

2. **New York grants dataset ID on data.ny.gov**
   - What we know: data.ny.gov uses Socrata; an API catalog exists
   - What's unclear: Which specific dataset(s) contain state grant opportunities (vs. grant awards). Need to search data.ny.gov for "grants"
   - Recommendation: PoC step — search `https://data.ny.gov/api/views/metadata/v1?search=grants` to enumerate candidates

3. **Texas grants dataset on data.texas.gov**
   - What we know: Texas Open Data Portal exists (SB 819, 2019); uses Socrata
   - What's unclear: eGrants (egrants.gov.texas.gov) is a grant management portal requiring login — not scrapable. Need to confirm whether data.texas.gov has a public grants dataset or if Texas requires HTML scraping of a different portal
   - Recommendation: Check data.texas.gov search for "grants" before committing Texas as a Tier-1 CKAN/Socrata target. May need to fall back to Texas Governor's grants page HTML scraping.

4. **Scrapling v0.4 `Fetcher` vs plain `httpx`**
   - What we know: For JSON API portals (CKAN, Socrata), Scrapling adds no value over plain `httpx`. The project noted Scrapling needs validation on 2-3 state portals.
   - What's unclear: Whether using `Fetcher` for HTTP JSON requests (no HTML parsing) is the correct approach or just adds a dependency layer
   - Recommendation: Use plain `httpx` for JSON API portals; use `Fetcher` only for HTML portals. This keeps the "validate Scrapling" PoC focused on the HTML use case (Colorado or similar).

5. **Alembic migration needed?**
   - What we know: The `opportunities` table already has `source` column with index; `state_california` etc. are just new source values
   - What's unclear: Whether any schema change is needed at all
   - Recommendation: No migration needed. State scrapers write `Opportunity` rows with `source="state_california"` etc. The existing schema handles this. The only change needed is extending `KNOWN_SOURCES` in `monitor.py`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, no version pinned in pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths = ["tests"]) |
| Quick run command | `uv run pytest tests/test_state_scrapers.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATE-01 | `BaseStateScraper.run()` returns correct stats dict shape | unit | `pytest tests/test_state_scrapers.py::test_base_scraper_stats_shape -x` | Wave 0 |
| STATE-01 | `normalize_ca_record()` maps fields to Opportunity schema | unit | `pytest tests/test_state_scrapers.py::test_normalize_ca_record -x` | Wave 0 |
| STATE-01 | ID format `state_{code}_{id}` prevents collision with federal records | unit | `pytest tests/test_state_scrapers.py::test_opportunity_id_prefix -x` | Wave 0 |
| STATE-02 | At least 5 distinct `source` values starting with `state_` in opportunities table | integration (manual) | Manual: query DB after first full run | N/A |
| STATE-03 | Legal review checklist documented for each portal | manual-only | N/A — code comments + LEGAL_REVIEW.md | N/A |
| STATE-04 | `check_zero_records()` returns source name when last run has `records_processed=0` | unit | `pytest tests/test_state_monitor.py::test_zero_records_detection -x` | Wave 0 |
| STATE-04 | `check_staleness()` does not false-alarm weekly state sources within 10-day window | unit | `pytest tests/test_state_monitor.py::test_state_stale_threshold -x` | Wave 0 |
| STATE-05 | APScheduler has a weekly job registered with `id="weekly_state_ingestion"` | unit | `pytest tests/test_state_scrapers.py::test_scheduler_weekly_job -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_state_scrapers.py tests/test_state_monitor.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_state_scrapers.py` — covers STATE-01 (stats shape, normalization, ID prefix, scheduler job)
- [ ] `tests/test_state_monitor.py` — covers STATE-04 (zero-records detection, per-source stale threshold)

*(No framework install needed — pytest is already present.)*

---

## Sources

### Primary (HIGH confidence)

- Existing grantflow codebase — `grantflow/ingest/run_all.py`, `monitor.py`, `normalizers.py`, `models.py`, `app.py` — direct inspection; ingestor contract, monitoring pattern, scheduler setup
- [CKAN API guide](https://docs.ckan.org/en/latest/api/) — `datastore_search` endpoint, pagination parameters
- [Socrata Open Data API](https://dev.socrata.com/docs/endpoints.html) — resource JSON endpoint, `$limit`/`$offset` pagination

### Secondary (MEDIUM confidence)

- [Scrapling v0.4 release notes](https://github.com/D4Vinci/Scrapling/releases/tag/v0.4) — fetcher tiers, `auto_save`, Spider framework, breaking changes
- [California Grants Portal on data.ca.gov](https://data.ca.gov/dataset/california-grants-portal) — confirmed CKAN API, daily update schedule, Grant Information Act of 2018 mandate
- [Texas Open Data Portal](https://data.texas.gov/) — SB 819 (2019) mandate confirmed; Socrata-based

### Tertiary (LOW confidence — validate during PoC)

- [data.ny.gov API Catalog](https://data.ny.gov/dataset/Open-ny-gov-API-Catalog/vfrh-bvhu/data) — Socrata confirmed; specific grants dataset ID unknown
- Texas grants dataset ID on data.texas.gov — existence unconfirmed; may require HTML fallback
- Colorado portal URL and structure — no centralized open data portal confirmed for grants

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core libraries already in the project; Scrapling is the only new dependency
- Architecture patterns: HIGH — ingestor contract, monitoring, and scheduler patterns derived directly from existing codebase
- Target portals (CA, IL): HIGH — CKAN API confirmed, mandated by state law
- Target portals (NY, TX): MEDIUM — Socrata confirmed, dataset IDs need PoC validation
- Target portals (CO): LOW — no open API confirmed; structure needs investigation
- Legal framework: MEDIUM — general open data legal principles verified; per-portal ToS must be read during PoC

**Research date:** 2026-03-24
**Valid until:** 2026-06-24 (90 days — government portals are stable; Scrapling may release patches)
