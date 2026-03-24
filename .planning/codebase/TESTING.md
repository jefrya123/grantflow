# Testing Patterns

**Analysis Date:** 2026-03-24

## Test Framework

**Runner:**
- pytest (configured in `pyproject.toml`)
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`
- `testpaths = ["tests"]`

**Assertion Library:**
- pytest built-in assertions (no third-party assertion library detected)

**Run Commands:**
```bash
uv run pytest              # Run all tests
uv run pytest -x           # Stop on first failure
uv run pytest -v           # Verbose output
uv run pytest --tb=short   # Short tracebacks
```

## Test File Organization

**Current State:**
- The `tests/` directory exists but contains no test files.
- Zero tests have been written for this codebase.

**Configured location:**
```
tests/           # Configured in pyproject.toml testpaths, currently empty
```

## What Needs Testing

Given the codebase structure, the following are the highest-value areas for test coverage:

### Unit Tests (pure functions — no DB or HTTP needed)

**`grantflow/ingest/grants_gov.py`:**
- `_normalize_date(value)` — multiple date format inputs, None input, invalid input
- `_parse_element(elem)` — XML element parsing, field type coercion, raw_data capture

**`grantflow/ingest/sbir.py`:**
- `_parse_date(value)` — date format variants, None/empty input
- `_make_award_key(row)` — key uniqueness, determinism

**`grantflow/web/routes.py`:**
- `_build_filters(...)` — filter dict construction, None coercion to empty string

**`grantflow/api/routes.py`:**
- `_opportunity_to_dict(o)` — field projection from model
- `_award_to_dict(a)` — field projection from model

### Integration Tests (require DB — use in-memory SQLite)

**`grantflow/api/routes.py`:**
- `search_opportunities` — pagination, filtering by status/agency/source, FTS search, sort/order
- `get_opportunity` — 404 for missing ID, award linkage via opportunity_number, fallback via cfda_numbers
- `get_stats` — aggregation correctness
- `get_agencies` — grouping and ordering

**`grantflow/web/routes.py`:**
- `search_page` — template rendering with filters
- `detail_page` — 404 handling, award linkage

### Ingest Pipeline Tests (require mocking HTTP)

**`grantflow/ingest/grants_gov.py`:**
- `ingest_grants_gov` — mock `httpx` to return fixture XML, verify upsert behavior, verify IngestionLog written
- `_upsert_batch` — insert new records, update existing records, stats increment correctly

**`grantflow/ingest/usaspending.py`:**
- `ingest_usaspending` — mock API responses, verify Award records created

**`grantflow/ingest/sbir.py`:**
- `ingest_sbir` — mock CSV download and solicitations API

## Recommended Test Structure

```
tests/
├── conftest.py              # Shared fixtures (in-memory DB, test client)
├── unit/
│   ├── test_grants_gov_parsers.py
│   ├── test_sbir_parsers.py
│   └── test_serializers.py
├── integration/
│   ├── test_api_opportunities.py
│   ├── test_api_stats.py
│   └── test_web_routes.py
└── ingest/
    ├── test_ingest_grants_gov.py
    ├── test_ingest_usaspending.py
    └── test_ingest_sbir.py
```

## Recommended Fixtures

**In-memory database (`tests/conftest.py`):**
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from grantflow.models import Base
from grantflow.app import app
from grantflow.database import get_db

@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

**Opportunity factory:**
```python
from grantflow.models import Opportunity

def make_opportunity(**kwargs) -> Opportunity:
    defaults = {
        "id": "grants_gov_12345",
        "source": "grants_gov",
        "source_id": "12345",
        "title": "Test Grant",
        "opportunity_status": "posted",
        "agency_code": "DOE",
        "agency_name": "Dept of Energy",
        "post_date": "2026-01-01",
        "close_date": "2026-04-01",
    }
    defaults.update(kwargs)
    return Opportunity(**defaults)
```

## Mocking

**Framework:** `unittest.mock` (stdlib) or `pytest-mock`

**HTTP mocking pattern (for ingest tests):**
```python
from unittest.mock import patch, MagicMock

def test_download_cached(tmp_path):
    with patch("grantflow.ingest.grants_gov.DATA_DIR", tmp_path):
        with patch("httpx.stream") as mock_stream:
            # set up mock response
            ...
```

**What to mock:**
- `httpx.get`, `httpx.head`, `httpx.stream` — all external HTTP calls in ingest modules
- `grantflow.config.DATA_DIR` — redirect file I/O to `tmp_path` in tests

**What NOT to mock:**
- SQLAlchemy session — use real in-memory SQLite instead
- FastAPI routing — use `TestClient` for real request/response cycle

## Mocking HTTP Responses

Ingest modules use `httpx` directly (not a shared client), so patch at the module level:

```python
# Patching grants_gov HTTP calls
with patch("grantflow.ingest.grants_gov.httpx.head") as mock_head:
    mock_head.return_value.status_code = 200
    ...

with patch("grantflow.ingest.grants_gov.httpx.stream") as mock_stream:
    mock_stream.return_value.__enter__ = ...
    ...
```

## Coverage

**Requirements:** None enforced (no `--cov` configuration in `pyproject.toml`)

**View coverage:**
```bash
uv run pytest --cov=grantflow --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Scope: Individual pure functions (date parsers, field mappers, serializers)
- No fixtures needed — pass inputs directly, assert outputs

**Integration Tests:**
- Scope: FastAPI route handlers with real in-memory SQLite
- Use `TestClient` for HTTP-level testing
- Seed data via session fixtures before each test

**E2E Tests:**
- Not configured or used

## Notes on Current State

- No tests exist. The `tests/` directory is empty.
- `pyproject.toml` has pytest configured with `testpaths = ["tests"]` but no plugins (no `pytest-mock`, `pytest-cov`, `httpx` test client extras).
- `httpx` is already a dependency and supports `httpx.MockTransport` for transport-level mocking if preferred over `unittest.mock`.
- FastAPI's `TestClient` (from `starlette.testclient`) is available via the `fastapi` dependency without additional installs.

---

*Testing analysis: 2026-03-24*
