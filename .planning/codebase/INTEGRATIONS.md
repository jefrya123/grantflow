# External Integrations

**Analysis Date:** 2026-03-24

## APIs & External Services

**Government Grant Data Sources (read-only, no auth required):**

- **Grants.gov XML Bulk Extract** - Full database of federal grant opportunities
  - Primary URL: `https://prod-grants-gov-chatbot.s3.amazonaws.com/extracts/GrantsDBExtract{YYYYMMDD}v2.zip`
  - Fallback scrape: `https://www.grants.gov/xml-extract`
  - Format: ZIP containing large XML file, parsed with `xml.etree.ElementTree` iterparse
  - Client: `httpx` streaming download (`grantflow/ingest/grants_gov.py`)
  - Auth: None
  - Schedule: Manual / on-demand; checks last 7 days for available extracts

- **USAspending.gov API** - Federal grant award data
  - Base URL: `https://api.usaspending.gov/api/v2` (configured in `grantflow/config.py` as `USASPENDING_API_BASE`)
  - Endpoint used: `POST /search/spending_by_award/`
  - Client: `httpx.Client` synchronous, paginated (100 records/page, max 5000 records)
  - Auth: None
  - Data scope: Grant/cooperative agreement type codes `["02", "03", "04", "05"]`, last 2 years
  - Implementation: `grantflow/ingest/usaspending.py`

- **SBIR.gov Awards CSV** - Small Business Innovation Research award data
  - URL: `https://data.www.sbir.gov/awarddatapublic/award_data.csv`
  - Format: CSV, streaming download, cached 24 hours at `data/sbir_award_data.csv`
  - Client: `httpx` streaming download
  - Auth: None
  - Implementation: `grantflow/ingest/sbir.py`

- **SBIR.gov Solicitations API** - Active SBIR/STTR solicitations
  - URL: `https://api.www.sbir.gov/public/api/solicitations`
  - Format: JSON (list or `{results: [...]}`)
  - Params: `rows=50`
  - Client: `httpx.get` synchronous
  - Auth: None
  - Implementation: `grantflow/ingest/sbir.py` (`_ingest_solicitations`)

## Data Storage

**Databases:**
- SQLite (via SQLAlchemy 2.0)
  - Connection string env var: `GRANTFLOW_DATABASE_URL` (default: `sqlite:///grantflow.db`)
  - Client/ORM: SQLAlchemy with `SessionLocal` session factory (`grantflow/database.py`)
  - WAL mode enabled via SQLite PRAGMA on connect
  - FTS5 virtual table: `opportunities_fts` for full-text search on `title`, `description`, `agency_name`, `category`
  - Tables: `opportunities`, `awards`, `agencies`, `ingestion_log`
  - Database files live in project root: `grantflow.db`, `grantflow.db-shm`, `grantflow.db-wal`

**File Storage:**
- Local filesystem only
  - Downloaded data cached at `data/` directory
  - Grants.gov ZIP and extracted XML: `data/GrantsDBExtract{date}.zip`, `data/*.xml`
  - SBIR CSV cache: `data/sbir_award_data.csv` (re-downloaded if older than 24 hours)

**Caching:**
- File-based only (no Redis or in-memory cache)
  - Grants.gov extract: indefinite cache (file presence check)
  - SBIR CSV: 24-hour TTL based on file mtime

## Authentication & Identity

**Auth Provider:**
- None — no user authentication implemented
- CORS is open (`allow_origins=["*"]`) — public read-only API

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry or similar)

**Logs:**
- Python stdlib `logging` module
- Log format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s` (set in `grantflow/ingest/run_all.py:main`)
- Ingestion status tracked in `ingestion_log` database table (source, started_at, completed_at, records_processed, records_added, records_updated, status, error)

## CI/CD & Deployment

**Hosting:**
- Not detected — no deployment config present

**CI Pipeline:**
- Not detected — no `.github/workflows`, `Dockerfile`, or CI config present

## Environment Configuration

**Required env vars:**
- None strictly required (all have defaults)

**Optional env vars:**
- `GRANTFLOW_DATABASE_URL` - Override SQLite path (e.g., for PostgreSQL)
- `GRANTFLOW_HOST` - Server bind host (default: `0.0.0.0`)
- `GRANTFLOW_PORT` - Server bind port (default: `8001`)
- `GRANTFLOW_ENV` - Environment name (default: `development`)

**Secrets location:**
- `.env` file in project root (gitignored per `.gitignore`)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-03-24*
