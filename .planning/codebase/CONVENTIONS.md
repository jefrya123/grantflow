# Coding Conventions

**Analysis Date:** 2026-03-24

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules (e.g., `grants_gov.py`, `run_all.py`)
- Modules named after the domain concept they serve

**Functions:**
- `snake_case` for all functions
- Private/internal helpers prefixed with underscore: `_normalize_date`, `_parse_element`, `_upsert_batch`, `_build_filters`, `_find_extract_url`
- Public entry points have no prefix: `ingest_grants_gov`, `run_all_ingestion`, `search_opportunities`

**Variables:**
- `snake_case` throughout
- Constants in `UPPER_SNAKE_CASE`: `FIELD_MAP`, `DATE_FIELDS`, `FLOAT_FIELDS`, `PER_PAGE`, `MAX_RECORDS`
- Loop variables are concise and contextual: `tag`, `value`, `row`, `elem`, `opp`

**Classes:**
- `PascalCase` for SQLAlchemy models: `Opportunity`, `Award`, `Agency`, `IngestionLog`
- `PascalCase` for FastAPI/Pydantic base classes: `Base` (DeclarativeBase subclass)

**Routes:**
- API routes use kebab-style path segments: `/api/v1/opportunities/search`, `/api/v1/opportunities/{opportunity_id}`
- Web routes mirror API paths without the prefix: `/search`, `/opportunity/{opportunity_id}`

## Code Style

**Formatting:**
- No formatter config detected (no `.prettierrc`, `black`, `ruff` config in `pyproject.toml`)
- Consistent 4-space indentation throughout
- Line breaks used for long function signatures — each parameter on its own line when signatures exceed ~80 chars

**Linting:**
- No linter configured (no `.flake8`, `.pylintrc`, `ruff` settings in `pyproject.toml`)
- `pyproject.toml` only contains `[tool.pytest.ini_options]`

**Type Annotations:**
- Used selectively on function signatures, particularly for public API functions
- Uses Python 3.10+ union syntax: `str | None` (not `Optional[str]`)
- Return types not consistently annotated (e.g., `-> dict`, `-> str | None`, `-> Path` used in some helpers; missing from most route handlers)
- No `from __future__ import annotations` used

## Import Organization

**Order (observed pattern):**
1. Standard library (`json`, `logging`, `re`, `zipfile`, `datetime`, `pathlib`, `csv`)
2. Third-party packages (`httpx`, `fastapi`, `sqlalchemy`)
3. Internal imports (`from grantflow.config import ...`, `from grantflow.database import ...`, `from grantflow.models import ...`)

**Path Aliases:**
- None — all internal imports use full package paths: `from grantflow.config import DATA_DIR`

**Deferred imports:**
- Occasionally used inside function bodies to avoid circular imports:
  `from sqlalchemy import text` inside `search_page` in `grantflow/web/routes.py`
  `from fastapi import HTTPException` inside `detail_page` in `grantflow/web/routes.py`
  `import hashlib` inside `_make_award_key` in `grantflow/ingest/sbir.py`

## Error Handling

**Pattern in ingest pipelines (`grantflow/ingest/grants_gov.py`, `grantflow/ingest/usaspending.py`, `grantflow/ingest/sbir.py`):**
- Broad `try/except Exception as e` wraps the full pipeline body
- Errors logged via `logger.exception(...)` which captures stack trace
- Error stored in stats dict: `stats["error"] = str(e)`
- Session rolled back on error: `session.rollback()`
- `finally` block always updates `IngestionLog` with completion status
- Nested `try/except Exception` in `finally` to prevent error during error handling

**Pattern in API routes (`grantflow/api/routes.py`):**
- FastAPI `HTTPException` raised for 404s: `raise HTTPException(status_code=404, detail="Opportunity not found")`
- No broad exception catching — FastAPI handles uncaught exceptions

**Pattern in helper functions:**
- Type coercion wrapped with `try/except (ValueError, TypeError)` returning `None` on failure
- Example from `grantflow/ingest/grants_gov.py`:
  ```python
  try:
      value = float(value) if value else None
  except (ValueError, TypeError):
      value = None
  ```

## Logging

**Framework:** Python standard library `logging`

**Setup pattern:**
- Module-level logger in every file: `logger = logging.getLogger(__name__)`
- CLI entry points configure root logger via `logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout)`

**Log levels used:**
- `logger.info(...)` — progress milestones, download status, record counts
- `logger.exception(...)` — caught exceptions (automatically includes traceback)

**Message formatting:**
- Uses `%`-style formatting (not f-strings) for log messages: `logger.info("Found extract at %s", url)`

## Comments

**Docstrings:**
- All public functions and module-level files have single-line or short docstring summaries
- Format: `"""Verb phrase describing what the function does."""`
- Examples: `"""Download and parse the Grants.gov XML bulk extract."""`, `"""Convert MM/DD/YYYY to YYYY-MM-DD."""`
- No parameters/returns sections — docstrings are brief descriptions only

**Inline comments:**
- Used to explain non-obvious logic (XML namespace stripping, FTS5 query pattern, batch size rationale)
- Section headers in longer functions use comment labels: `# Apply filters`, `# Count total before pagination`, `# Sort`, `# Paginate`

## Function Design

**Size:** Route handlers are long (50-100 lines) due to inline filter logic. Helper functions are short (5-30 lines).

**Parameters:** Query parameters passed individually, not as a grouped object. FastAPI `Depends(get_db)` used for DB injection.

**Return values:**
- Route handlers return plain dicts (FastAPI serializes to JSON automatically)
- Ingest functions return a `stats` dict with consistent keys: `source`, `status`, `records_processed`, `records_added`, `records_updated`, `error`
- Helper parsers return `None` on failure rather than raising

## Module Design

**Exports:**
- No explicit `__all__` in any module
- `grantflow/__init__.py` and `grantflow/api/__init__.py`, `grantflow/ingest/__init__.py`, `grantflow/web/__init__.py` are all empty

**Configuration:**
- All config in `grantflow/config.py` as module-level constants; imported directly where needed
- No config classes or dataclasses — plain module globals

**Data mapping:**
- Field mappings defined as module-level `dict` constants (`FIELD_MAP`, `CSV_FIELD_MAP`) in each ingest module
- Type-casting sets defined as module-level `set` constants (`DATE_FIELDS`, `FLOAT_FIELDS`, etc.)

**Serialization:**
- Models serialized via private `_opportunity_to_dict` / `_award_to_dict` helper functions in `grantflow/api/routes.py`
- No Pydantic response models used for API output — raw dicts returned

---

*Convention analysis: 2026-03-24*
