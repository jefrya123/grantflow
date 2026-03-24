# GrantFlow MVP — Overnight Build Plan

## What We're Building
A unified government grants & contracts data API that wraps broken federal APIs
(grants.gov, USAspending, SBIR) into one clean, searchable interface.

## Architecture
```
Data Sources → Ingestion Scripts → SQLite (FTS5) → FastAPI → Jinja2 Search Page
```

## Tech Stack
- Python 3.12+ / uv
- FastAPI + Uvicorn
- SQLAlchemy 2.0 + SQLite (WAL + FTS5)
- Scrapling (installed for Phase 2 state scraping)
- Jinja2 templates (server-rendered, same pattern as AgentGrade)
- No auth, no Stripe, no billing — just data + API + search

## Project Structure
```
/home/jeff/Projects/grantflow/
├── pyproject.toml
├── plan.md
├── README.md
├── .env
├── .gitignore
├── grantflow/
│   ├── __init__.py
│   ├── app.py                 # FastAPI app entry point
│   ├── config.py              # Environment config
│   ├── database.py            # SQLAlchemy engine + session
│   ├── models.py              # SQLAlchemy models (Opportunity, Award, Agency)
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── grants_gov.py      # Grants.gov XML extract parser
│   │   ├── usaspending.py     # USAspending API client
│   │   ├── sbir.py            # SBIR CSV parser
│   │   └── run_all.py         # Orchestrator: run all ingestion
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # FastAPI routes (/search, /{id}, /stats)
│   └── web/
│       ├── __init__.py
│       └── routes.py          # Web UI routes (search page)
├── templates/
│   ├── base.html              # Base layout
│   ├── search.html            # Search + results page
│   └── detail.html            # Single opportunity detail
└── static/
    └── style.css              # Minimal CSS
```

## Database Schema

### opportunities (main table)
```sql
CREATE TABLE opportunities (
    id TEXT PRIMARY KEY,              -- our internal ID (source_type + source_id)
    source TEXT NOT NULL,             -- 'grants_gov', 'sam_gov', 'sbir', 'usaspending'
    source_id TEXT NOT NULL,          -- original ID from source
    title TEXT NOT NULL,
    description TEXT,
    agency_code TEXT,
    agency_name TEXT,
    opportunity_number TEXT,          -- funding opportunity number
    opportunity_status TEXT,          -- posted, closed, archived, forecasted
    funding_instrument TEXT,          -- grant, cooperative_agreement, contract, other
    category TEXT,                    -- normalized category
    cfda_numbers TEXT,                -- comma-separated CFDA/ALN numbers
    eligible_applicants TEXT,         -- JSON array of eligible applicant types
    post_date TEXT,                   -- ISO 8601
    close_date TEXT,                  -- ISO 8601
    last_updated TEXT,                -- ISO 8601
    award_floor REAL,
    award_ceiling REAL,
    estimated_total_funding REAL,
    expected_number_of_awards INTEGER,
    cost_sharing_required BOOLEAN,
    contact_email TEXT,
    contact_text TEXT,
    additional_info_url TEXT,
    source_url TEXT,                  -- link back to original
    raw_data TEXT,                    -- full JSON dump for future use
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_opp_source ON opportunities(source);
CREATE INDEX idx_opp_status ON opportunities(opportunity_status);
CREATE INDEX idx_opp_agency ON opportunities(agency_code);
CREATE INDEX idx_opp_close ON opportunities(close_date);
CREATE INDEX idx_opp_post ON opportunities(post_date);
```

### opportunities_fts (full-text search)
```sql
CREATE VIRTUAL TABLE opportunities_fts USING fts5(
    title, description, agency_name, category,
    content='opportunities',
    content_rowid='rowid'
);
```

### awards (historical award data from USAspending)
```sql
CREATE TABLE awards (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,              -- 'usaspending', 'sbir'
    award_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    agency_code TEXT,
    agency_name TEXT,
    cfda_numbers TEXT,
    recipient_name TEXT,
    recipient_uei TEXT,
    award_amount REAL,
    total_funding REAL,
    award_date TEXT,                   -- ISO 8601
    start_date TEXT,
    end_date TEXT,
    place_state TEXT,
    place_city TEXT,
    place_country TEXT,
    opportunity_number TEXT,           -- links back to opportunities
    award_type TEXT,                   -- grant, contract, cooperative_agreement
    raw_data TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_award_cfda ON awards(cfda_numbers);
CREATE INDEX idx_award_opp ON awards(opportunity_number);
CREATE INDEX idx_award_agency ON awards(agency_code);
CREATE INDEX idx_award_recipient ON awards(recipient_name);
```

### agencies (reference table)
```sql
CREATE TABLE agencies (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_code TEXT,
    parent_name TEXT
);
```

### ingestion_log (track ingestion runs)
```sql
CREATE TABLE ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    records_processed INTEGER DEFAULT 0,
    records_added INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',     -- running, completed, failed
    error TEXT
);
```

## API Endpoints

### Search
```
GET /api/v1/opportunities/search
  ?q=clean+energy              -- full-text search
  &status=posted               -- filter by status
  &agency=DOE                  -- filter by agency
  &eligible=small_business     -- filter by eligibility
  &category=environment        -- filter by category
  &min_award=10000             -- minimum award floor
  &max_award=1000000           -- maximum award ceiling
  &closing_after=2026-04-01    -- deadline filter
  &closing_before=2026-06-01
  &source=grants_gov,sbir      -- filter by data source
  &sort=close_date             -- sort field
  &order=asc                   -- sort direction
  &page=1                      -- pagination
  &per_page=20
```

### Detail
```
GET /api/v1/opportunities/{id}
  -- returns full opportunity + linked historical awards
```

### Stats
```
GET /api/v1/stats
  -- total opportunities, by source, by status, by agency
  -- total award $ available
  -- closing soon count
```

### Agencies
```
GET /api/v1/agencies
  -- list all agencies with opportunity counts
```

## Data Ingestion Details

### 1. Grants.gov XML Extract
- Download: https://www.grants.gov/xml-extract (daily zip)
- Parse XML using ElementTree
- Extract all 30 fields from OpportunitySynopsisDetail schema
- Normalize dates to ISO 8601
- Normalize eligible applicant codes to human-readable strings
- Upsert into opportunities table (source='grants_gov')

### 2. USAspending.gov API
- Base: https://api.usaspending.gov/api/v2/
- No auth required, generous rate limits
- Use /search/spending_by_award/ to get recent grant awards
- Use /awards/{id}/ for full detail
- Pull last 2 years of grant awards
- Store in awards table, link via CFDA/opportunity_number
- Build historical stats per opportunity/agency

### 3. SBIR.gov
- Bulk CSV: https://data.www.sbir.gov/awarddatapublic/award_data.csv (~290MB)
- Also solicitations API: https://api.www.sbir.gov/public/api/solicitations
- Parse CSV for awards, API for active solicitations
- Awards → awards table
- Solicitations → opportunities table (source='sbir')

## Ingestion Run Order
1. Grants.gov XML (largest, most important)
2. SBIR solicitations + awards
3. USAspending historical awards
4. Cross-reference: link awards to opportunities via CFDA numbers

## Web UI
- Single search page with filters (same Jinja2 pattern as AgentGrade)
- Detail page showing opportunity + historical awards
- No login, no accounts — fully public
- Clean, minimal CSS

## Deployment
- Same VPS (5.161.92.74) as AgentGrade
- Separate systemd service (grantflow)
- Separate port (8001, Caddy proxies grantflow.dev or similar)
- GitHub repo + Actions deploy (copy AgentGrade pattern)

## Phase 2 (after MVP)
- State grant scraping with Scrapling (top 10 states)
- Ruflo agent orchestration for daily pipeline
- Email digest alerts (closing soon)
- API keys + rate limiting
- Stripe billing

## Checkpoints
After each step, the builder should verify:
- [ ] Step 1: `uv run python -c "from grantflow.app import app; print('OK')"` works
- [ ] Step 2: Ingestion scripts download and parse without errors
- [ ] Step 3: Database has records, FTS search returns results
- [ ] Step 4: API endpoints return JSON
- [ ] Step 5: Search page renders in browser
- [ ] Step 6: Deploy to VPS, accessible via HTTP
