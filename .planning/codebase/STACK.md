# Technology Stack

**Analysis Date:** 2026-03-24

## Languages

**Primary:**
- Python 3.12+ - All application code (API, ingestion, web UI)

**Templates:**
- Jinja2 HTML - Server-side rendered web UI (`templates/`)

## Runtime

**Environment:**
- CPython 3.12+

**Package Manager:**
- uv
- Lockfile: `uv.lock` (present, committed)

## Frameworks

**Core:**
- FastAPI 0.135.2 - HTTP API and web routing (`grantflow/app.py`)
- Starlette 1.0.0 - ASGI foundation (pulled in by FastAPI)
- Pydantic 2.12.5 - Data validation and settings

**Web/Templating:**
- Jinja2 3.1.6 - HTML templates served via `fastapi.templating.Jinja2Templates`
- FastAPI StaticFiles - Serves `static/` directory at `/static`

**Database ORM:**
- SQLAlchemy 2.0.48 - ORM and query engine (`grantflow/database.py`, `grantflow/models.py`)

**HTTP Client:**
- httpx 0.28.1 - All outbound HTTP requests in ingest pipelines (sync and streaming)

**Server:**
- uvicorn 0.42.0 with standard extras (uvloop, httptools, watchfiles, websockets)
- Run via: `uvicorn grantflow.app:app --reload`

**Testing:**
- pytest (via `[tool.pytest.ini_options]` in `pyproject.toml`, testpaths = `tests/`)

**Build/Dev:**
- uv - Dependency management and virtual env (`pyproject.toml`)
- python-dotenv 1.2.2 - `.env` file loading at startup (`grantflow/config.py`)

## Key Dependencies

**Critical:**
- `fastapi>=0.115.0` - Core web framework; all routes depend on it
- `sqlalchemy>=2.0` - All database access; ORM + raw SQL for FTS queries
- `httpx>=0.27` - All external data fetching; used in streaming mode for large downloads
- `lxml>=5.0` - Available but stdlib `xml.etree.ElementTree` is used for XML parsing

**Infrastructure:**
- `pydantic>=2.0` - Request/response validation via FastAPI
- `jinja2>=3.1` - Web UI templates (`templates/search.html`, `templates/detail.html`, `templates/base.html`)
- `uvicorn[standard]>=0.34.0` - Production-capable ASGI server with uvloop

## Configuration

**Environment:**
- Loaded via `python-dotenv` from `.env` at import time in `grantflow/config.py`
- Key config variables:
  - `GRANTFLOW_ENV` - Environment name (default: `development`)
  - `GRANTFLOW_DATABASE_URL` - SQLAlchemy connection string (default: `sqlite:///grantflow.db`)
  - `GRANTFLOW_HOST` - Bind host (default: `0.0.0.0`)
  - `GRANTFLOW_PORT` - Bind port (default: `8001`)

**Build:**
- `pyproject.toml` - Project metadata, dependencies, pytest config
- `uv.lock` - Pinned dependency tree

## Platform Requirements

**Development:**
- Python 3.12+
- uv package manager
- Run server: `uv run grantflow` (entry point: `grantflow.app:main`)
- Run ingestion: `uv run python -m grantflow.ingest.run_all`

**Production:**
- SQLite with WAL mode enabled (pragmas set on connect in `grantflow/database.py`)
- Single-process deployment; no async task queue — ingestion runs synchronously
- Database files: `grantflow.db`, `grantflow.db-shm`, `grantflow.db-wal` in project root

---

*Stack analysis: 2026-03-24*
