# Codebase Structure

**Analysis Date:** 2026-03-24

## Directory Layout

```
grantflow/                      # Project root
├── grantflow/                  # Main Python package
│   ├── __init__.py
│   ├── app.py                  # FastAPI app factory + entry point
│   ├── config.py               # Env vars, paths, external API URLs
│   ├── database.py             # SQLAlchemy engine, session, init_db
│   ├── models.py               # ORM models (Opportunity, Award, Agency, IngestionLog)
│   ├── api/                    # JSON REST API layer
│   │   ├── __init__.py
│   │   └── routes.py           # /api/v1/* endpoints
│   ├── ingest/                 # Data ingestion pipeline
│   │   ├── __init__.py
│   │   ├── grants_gov.py       # Grants.gov XML bulk extract ingestor
│   │   ├── usaspending.py      # USAspending.gov API ingestor
│   │   ├── sbir.py             # SBIR awards CSV + solicitations API ingestor
│   │   └── run_all.py          # Orchestrator + CLI entry point
│   └── web/                    # Server-rendered HTML layer
│       ├── __init__.py
│       └── routes.py           # /search, /opportunity/{id} HTML pages
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Base layout with nav/footer
│   ├── search.html             # Search results + filter form
│   └── detail.html             # Single opportunity detail view
├── static/                     # Static assets served at /static
│   └── style.css               # All CSS (single file)
├── data/                       # Downloaded source data files (gitignored)
│   ├── GrantsDBExtract*.zip    # Grants.gov bulk zip (cached)
│   ├── GrantsDBExtract*.xml    # Grants.gov extracted XML
│   └── sbir_award_data.csv     # SBIR awards CSV
├── tests/                      # Test suite (currently empty)
├── .planning/                  # GSD planning artifacts
│   └── codebase/               # Codebase analysis documents
├── grantflow.db                # SQLite database (project root)
├── grantflow.db-shm            # SQLite WAL shared memory
├── grantflow.db-wal            # SQLite WAL log
├── pyproject.toml              # Project metadata, dependencies, scripts
├── uv.lock                     # Dependency lockfile
├── plan.md                     # Project planning document
├── .env                        # Local environment overrides (gitignored)
├── .gitignore
└── .venv/                      # Virtual environment (gitignored)
```

## Directory Purposes

**`grantflow/` (package root):**
- Purpose: Core application code
- Contains: App factory, config, database layer, ORM models
- Key files: `app.py`, `config.py`, `database.py`, `models.py`

**`grantflow/api/`:**
- Purpose: JSON REST API endpoints
- Contains: Single `routes.py` with all `/api/v1/*` handlers
- Key files: `grantflow/api/routes.py`

**`grantflow/web/`:**
- Purpose: Browser-facing HTML routes using Jinja2
- Contains: Single `routes.py` with search and detail page handlers
- Key files: `grantflow/web/routes.py`

**`grantflow/ingest/`:**
- Purpose: Data pipeline — download, parse, normalize, upsert from government sources
- Contains: One module per source, plus `run_all.py` orchestrator
- Key files: `grantflow/ingest/grants_gov.py`, `grantflow/ingest/usaspending.py`, `grantflow/ingest/sbir.py`, `grantflow/ingest/run_all.py`

**`templates/`:**
- Purpose: Jinja2 HTML templates rendered by `grantflow/web/routes.py`
- Contains: `base.html` layout, `search.html`, `detail.html`
- Generated: No — hand-authored

**`static/`:**
- Purpose: Served verbatim at `/static` by FastAPI `StaticFiles` mount
- Contains: `style.css` (single stylesheet)
- Generated: No

**`data/`:**
- Purpose: Local cache for downloaded source data files
- Contains: Grants.gov zip/XML, SBIR CSV
- Generated: Yes — populated by ingest pipeline; gitignored

**`tests/`:**
- Purpose: Pytest test suite
- Contains: Currently empty
- Generated: No

## Key File Locations

**Entry Points:**
- `grantflow/app.py`: ASGI app object + `main()` for uvicorn server
- `grantflow/ingest/run_all.py`: Ingestion pipeline CLI `main()`

**Configuration:**
- `grantflow/config.py`: All env vars, path constants, external API base URLs
- `pyproject.toml`: Dependencies, Python version requirement, CLI scripts
- `.env`: Local overrides for `GRANTFLOW_ENV`, `GRANTFLOW_DATABASE_URL`, `GRANTFLOW_HOST`, `GRANTFLOW_PORT`

**Core Logic:**
- `grantflow/models.py`: All SQLAlchemy ORM models
- `grantflow/database.py`: Engine, session factory, `get_db()` dependency, `init_db()`
- `grantflow/api/routes.py`: All JSON API handlers + serializer helpers
- `grantflow/web/routes.py`: All HTML page handlers

**Testing:**
- `tests/`: Empty — no tests exist yet

## Naming Conventions

**Files:**
- snake_case for all Python modules: `grants_gov.py`, `run_all.py`, `routes.py`
- One concern per file within `ingest/` (one file per data source)
- Both `api/` and `web/` use the same filename `routes.py` for their router module

**Directories:**
- Lowercase, no separators: `api/`, `web/`, `ingest/`, `templates/`, `static/`, `data/`

**Models:**
- PascalCase class names: `Opportunity`, `Award`, `Agency`, `IngestionLog`
- snake_case column names matching database column names

**Functions:**
- Public ingest functions: `ingest_{source_name}()` pattern — `ingest_grants_gov()`, `ingest_usaspending()`, `ingest_sbir()`
- Private helpers: leading underscore — `_upsert_batch()`, `_parse_element()`, `_build_filters()`, `_normalize_date()`
- Serializers: `_opportunity_to_dict()`, `_award_to_dict()` in `grantflow/api/routes.py`

**IDs:**
- Opportunity primary keys: `{source}_{source_id}` (e.g., `grants_gov_12345`, `sbir_ABC-001`)
- Award primary keys: same `{source}_{award_id}` pattern

## Where to Add New Code

**New ingest source:**
- Implementation: `grantflow/ingest/{source_name}.py` — implement `ingest_{source_name}() -> dict` returning standard stats dict
- Register in: `grantflow/ingest/run_all.py` → `run_all_ingestion()`

**New API endpoint:**
- Implementation: `grantflow/api/routes.py` — add route to existing `router`
- No new file needed unless module grows significantly

**New HTML page:**
- Template: `templates/{page_name}.html` extending `base.html`
- Route handler: `grantflow/web/routes.py` — add route to existing `router`

**New ORM model:**
- Implementation: `grantflow/models.py` — add class extending `Base`
- Migration: `init_db()` in `grantflow/database.py` calls `Base.metadata.create_all()` on startup (additive only — no migration tooling exists)

**New configuration value:**
- Add env var read: `grantflow/config.py`
- Document env var name in `.env` example

**Utilities shared across modules:**
- Currently no `utils.py` exists — add `grantflow/utils.py` for shared helpers

## Special Directories

**`data/`:**
- Purpose: Cache for large downloaded files (Grants.gov XML ~300MB, SBIR CSV ~350MB)
- Generated: Yes, by ingest pipeline
- Committed: No (gitignored)

**`.venv/`:**
- Purpose: uv-managed virtual environment
- Generated: Yes
- Committed: No

**`.planning/`:**
- Purpose: GSD planning and codebase analysis documents
- Generated: Yes, by GSD tooling
- Committed: Yes (planning artifacts)

**`grantflow.db` / `grantflow.db-shm` / `grantflow.db-wal`:**
- Purpose: SQLite database with WAL journaling mode
- Location: Project root (controlled by `GRANTFLOW_DATABASE_URL` env var)
- Committed: No (gitignored)

---

*Structure analysis: 2026-03-24*
