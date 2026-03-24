# Architecture

**Analysis Date:** 2026-03-24

## Pattern Overview

**Overall:** Monolithic FastAPI application with dual interface (JSON API + server-rendered HTML) backed by a single SQLite database, plus a standalone data ingestion pipeline.

**Key Characteristics:**
- Single Python process serves both REST API and Jinja2-rendered web UI
- No service layer — route handlers query SQLite directly via SQLAlchemy ORM
- Ingestion pipeline is decoupled from the web server; runs as a CLI command
- FTS5 virtual table provides full-text search inside SQLite
- All data normalized into two primary domain models: `Opportunity` and `Award`

## Layers

**Configuration:**
- Purpose: Environment and path resolution
- Location: `grantflow/config.py`
- Contains: Env var loading, base paths, external API URLs
- Depends on: `python-dotenv`
- Used by: All other modules

**Data Models:**
- Purpose: SQLAlchemy ORM definitions and database schema
- Location: `grantflow/models.py`
- Contains: `Opportunity`, `Award`, `Agency`, `IngestionLog` model classes
- Depends on: SQLAlchemy `DeclarativeBase`
- Used by: Routes, ingest modules, database init

**Database:**
- Purpose: Engine, session factory, DB initialization including FTS5 table creation
- Location: `grantflow/database.py`
- Contains: `engine`, `SessionLocal`, `get_db()` dependency, `init_db()`
- Depends on: `grantflow/config.py`, `grantflow/models.py`
- Used by: Route modules, ingest modules, `run_all.py`

**API Routes (JSON):**
- Purpose: REST JSON endpoints for programmatic access
- Location: `grantflow/api/routes.py`
- Contains: `/api/v1/opportunities/search`, `/api/v1/opportunities/{id}`, `/api/v1/stats`, `/api/v1/agencies`
- Depends on: `grantflow/models.py`, `grantflow/database.py`
- Used by: External API consumers, OpenAPI docs at `/docs`

**Web Routes (HTML):**
- Purpose: Server-side rendered HTML pages via Jinja2
- Location: `grantflow/web/routes.py`
- Contains: `GET /` (redirect), `GET /search`, `GET /opportunity/{id}`
- Depends on: `grantflow/models.py`, `grantflow/database.py`, `templates/`
- Used by: Browser clients

**Ingest Modules:**
- Purpose: Download, parse, and upsert data from external government sources
- Location: `grantflow/ingest/`
- Contains: `grants_gov.py`, `usaspending.py`, `sbir.py`, `run_all.py`
- Depends on: `grantflow/config.py`, `grantflow/database.py`, `grantflow/models.py`
- Used by: CLI via `run_all.main()`, standalone execution

**Application Entry Point:**
- Purpose: FastAPI app instantiation, middleware, router registration, lifespan
- Location: `grantflow/app.py`
- Contains: `app` instance, CORS middleware, static file mount, router includes
- Depends on: All route modules, `grantflow/database.py`, `grantflow/config.py`

## Data Flow

**Search Request (API):**

1. HTTP request hits `GET /api/v1/opportunities/search` in `grantflow/api/routes.py`
2. If `q` param present: raw SQL FTS5 query against `opportunities_fts` virtual table returns matching rowids
3. SQLAlchemy ORM query on `opportunities` table filters by rowids + any additional filter params
4. Results paginated, serialized via `_opportunity_to_dict()`, returned as JSON

**Search Request (Web):**

1. HTTP request hits `GET /search` in `grantflow/web/routes.py`
2. Identical FTS5 + ORM query logic as API layer (duplicated code)
3. Result set passed to Jinja2 `search.html` template; rendered HTML returned

**Detail View:**

1. `GET /opportunity/{id}` (web) or `GET /api/v1/opportunities/{id}` (API)
2. ORM lookup by primary key
3. Related `Award` records fetched by `opportunity_number` match, falling back to `cfda_numbers` ilike match
4. Returned as HTML template or JSON dict with embedded `awards` list

**Ingestion Pipeline:**

1. CLI entry via `uv run grantflow-ingest` or `python -m grantflow.ingest.run_all`
2. `run_all.run_all_ingestion()` calls `init_db()` then invokes each source ingestor in sequence
3. Each ingestor: discovers/downloads source data → parses into normalized dicts → upserts to `opportunities` or `awards` table in batches of 500 → writes `IngestionLog` record
4. After all sources complete, `_rebuild_fts()` repopulates `opportunities_fts` virtual table
5. Stats dict returned and printed to stdout

**State Management:**
- All persistent state lives in `grantflow.db` (SQLite file at project root)
- WAL mode enabled for concurrent read/write during ingestion + serving
- No in-memory caching layer

## Key Abstractions

**Opportunity:**
- Purpose: Unified representation of a grant funding opportunity regardless of source
- Examples: `grantflow/models.py` (`Opportunity` class)
- Pattern: Flat SQLAlchemy model; source-specific fields stored as JSON in `raw_data` (Text column); composite ID `{source}_{source_id}`

**Award:**
- Purpose: Represents a completed/active grant award from any source
- Examples: `grantflow/models.py` (`Award` class)
- Pattern: Same flat model pattern as `Opportunity`; linked to opportunities via `opportunity_number` or `cfda_numbers`

**IngestionLog:**
- Purpose: Audit trail for each pipeline run per source
- Examples: `grantflow/models.py` (`IngestionLog` class)
- Pattern: Written at start of run with `status="running"`, updated in `finally` block

**Ingest function contract:**
- Purpose: Uniform interface for all source ingestors
- Examples: `ingest_grants_gov()`, `ingest_usaspending()`, `ingest_sbir()` in `grantflow/ingest/`
- Pattern: Each returns a stats dict with keys `status`, `records_processed`, `records_added`, `records_updated`, `error`

**`get_db()` dependency:**
- Purpose: SQLAlchemy session lifecycle for FastAPI route handlers
- Examples: `grantflow/database.py`
- Pattern: Generator yielding `Session`, always closed in `finally`; injected via `Depends(get_db)`

## Entry Points

**Web Server:**
- Location: `grantflow/app.py` → `main()`
- Triggers: `uv run grantflow` (via `[project.scripts]` in `pyproject.toml`)
- Responsibilities: Starts uvicorn on configured host/port with reload; calls `init_db()` on lifespan startup

**Ingestion CLI:**
- Location: `grantflow/ingest/run_all.py` → `main()`
- Triggers: `python -m grantflow.ingest.run_all` or direct execution
- Responsibilities: Runs all three ingest pipelines sequentially, rebuilds FTS index, prints summary

**FastAPI app object:**
- Location: `grantflow/app.py` → `app`
- Triggers: Imported by uvicorn as `"grantflow.app:app"`
- Responsibilities: ASGI application; mounts static files at `/static`, includes API router at `/api/v1` and web router at `/`

## Error Handling

**Strategy:** Try/except with rollback at the ingest layer; HTTP exceptions raised directly from route handlers; no global error middleware.

**Patterns:**
- Ingest functions catch all exceptions, log via `logger.exception()`, set `stats["status"] = "error"`, rollback session, and return stats dict (never raise)
- Route handlers raise `HTTPException(status_code=404)` for missing records
- Database session always closed in `finally` block in both `get_db()` and ingest code
- `IngestionLog.error` stores first 100 chars of exception message

## Cross-Cutting Concerns

**Logging:** stdlib `logging` module; each module gets `logger = logging.getLogger(__name__)`; ingestion CLI configures `basicConfig` to stdout with timestamps
**Validation:** FastAPI/Pydantic validates query parameters (types, ranges via `Query(ge=1, le=100)`); no request body validation needed (all reads)
**Authentication:** None — all endpoints are public, CORS set to `allow_origins=["*"]`

---

*Architecture analysis: 2026-03-24*
