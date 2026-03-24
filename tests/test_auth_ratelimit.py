"""Tests for API key authentication and rate limiting (Plan 03-02)."""
import hashlib
import pytest
from fastapi.testclient import TestClient

from grantflow.app import app
from grantflow.database import get_db
from grantflow.models import ApiKey, Base


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def make_key(db, tier: str = "free", key_suffix: str = "") -> str:
    """Create an ApiKey row in the test DB and return the plaintext key."""
    import datetime
    plaintext = f"testkey_{tier}{key_suffix}"
    row = ApiKey(
        key_hash=_hash(plaintext),
        key_prefix=plaintext[:8],
        tier=tier,
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        last_used_at=None,
        request_count=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return plaintext


# ---------------------------------------------------------------------------
# Unit-level tests for get_api_key() dependency
# ---------------------------------------------------------------------------

def test_missing_key(client):
    """No X-API-Key header → 401 MISSING_API_KEY."""
    from grantflow.api.auth import get_api_key
    from fastapi import Header
    import inspect

    # Call via endpoint to test the full FastAPI dependency chain
    # We test this via the protected /opportunities/search endpoint (added in Task 2).
    # For now, test that the dependency itself is importable and has correct signature.
    sig = inspect.signature(get_api_key)
    params = list(sig.parameters.keys())
    assert "x_api_key" in params
    assert "db" in params


def test_invalid_key(client, db_session):
    """Unknown key hash → 401 INVALID_API_KEY."""
    from grantflow.api.auth import get_api_key
    from fastapi import HTTPException
    import asyncio

    # Patch db with test session
    async def run():
        try:
            await get_api_key(x_api_key="totally_wrong_key", db=db_session)
            return None
        except HTTPException as e:
            return e

    exc = asyncio.run(run())
    assert exc is not None
    assert exc.status_code == 401
    assert exc.detail["error_code"] == "INVALID_API_KEY"


def test_valid_key(client, db_session):
    """Valid key → returns ApiKey row with correct tier."""
    from grantflow.api.auth import get_api_key
    import asyncio

    plaintext = make_key(db_session, tier="free")

    async def run():
        return await get_api_key(x_api_key=plaintext, db=db_session)

    result = asyncio.run(run())
    assert result is not None
    assert result.tier == "free"
    assert result.is_active is True


def test_missing_key_header_returns_none(client, db_session):
    """None x_api_key → 401 MISSING_API_KEY."""
    from grantflow.api.auth import get_api_key
    from fastapi import HTTPException
    import asyncio

    async def run():
        try:
            await get_api_key(x_api_key=None, db=db_session)
            return None
        except HTTPException as e:
            return e

    exc = asyncio.run(run())
    assert exc is not None
    assert exc.status_code == 401
    assert exc.detail["error_code"] == "MISSING_API_KEY"


# ---------------------------------------------------------------------------
# Integration tests: auth wired to endpoints (Task 2)
# ---------------------------------------------------------------------------

def test_protected_endpoint_without_key(client):
    """GET /api/v1/opportunities/search without X-API-Key → 401."""
    resp = client.get("/api/v1/opportunities/search")
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"]["error_code"] == "MISSING_API_KEY"


def test_protected_endpoint_with_valid_key(client, db_session):
    """GET /api/v1/opportunities/search with valid key → 200."""
    plaintext = make_key(db_session, tier="free", key_suffix="_integ")
    resp = client.get(
        "/api/v1/opportunities/search",
        headers={"X-API-Key": plaintext},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data


def test_health_remains_public(client):
    """GET /api/v1/health without X-API-Key → 200 (public endpoint)."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


def test_docs_remain_public(client):
    """GET /docs without X-API-Key → 200 (OpenAPI docs are public)."""
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_stats_endpoint_requires_key(client):
    """GET /api/v1/stats without key → 401."""
    resp = client.get("/api/v1/stats")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "MISSING_API_KEY"


def test_agencies_endpoint_requires_key(client):
    """GET /api/v1/agencies without key → 401."""
    resp = client.get("/api/v1/agencies")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "MISSING_API_KEY"


# ---------------------------------------------------------------------------
# Tier-aware rate limit callable tests (Plan 09-01)
# ---------------------------------------------------------------------------

@pytest.fixture()
def patched_session_factory(db_session, monkeypatch):
    """Redirect auth._session_factory to the test DB so _tier_limit queries it."""
    import grantflow.api.auth as auth_mod
    from sqlalchemy.orm import sessionmaker

    # Build a factory that returns the same test session (wraps it so close() is no-op)
    class _BoundSession:
        """Proxy that delegates to db_session but ignores close() to avoid teardown."""
        def __init__(self, session):
            self._s = session

        def query(self, *a, **kw):
            return self._s.query(*a, **kw)

        def close(self):
            pass  # let conftest handle teardown

    def _factory():
        return _BoundSession(db_session)

    monkeypatch.setattr(auth_mod, "_session_factory", _factory)
    return db_session


def test_tier_limit_free(patched_session_factory):
    """_tier_limit() returns '1000/day' for a free-tier API key."""
    from grantflow.api.auth import _tier_limit

    plaintext = make_key(patched_session_factory, tier="free", key_suffix="_tl_free")
    result = _tier_limit(plaintext)
    assert result == "1000/day"


def test_tier_limit_starter(patched_session_factory):
    """_tier_limit() returns '10000/day' for a starter-tier API key."""
    from grantflow.api.auth import _tier_limit

    plaintext = make_key(patched_session_factory, tier="starter", key_suffix="_tl_starter")
    result = _tier_limit(plaintext)
    assert result == "10000/day"


def test_tier_limit_growth(patched_session_factory):
    """_tier_limit() returns '100000/day' for a growth-tier API key."""
    from grantflow.api.auth import _tier_limit

    plaintext = make_key(patched_session_factory, tier="growth", key_suffix="_tl_growth")
    result = _tier_limit(plaintext)
    assert result == "100000/day"


def test_tier_limit_unknown_key(patched_session_factory):
    """_tier_limit() returns '1000/day' (free default) for an unknown key."""
    from grantflow.api.auth import _tier_limit

    result = _tier_limit("totally_unknown_key_xyz_12345")
    assert result == "1000/day"


def test_tier_export_limit_free(patched_session_factory):
    """_tier_export_limit() returns '100/day' for a free-tier key."""
    from grantflow.api.auth import _tier_export_limit

    plaintext = make_key(patched_session_factory, tier="free", key_suffix="_tel_free")
    result = _tier_export_limit(plaintext)
    assert result == "100/day"


def test_tier_export_limit_growth(patched_session_factory):
    """_tier_export_limit() returns '10000/day' for a growth-tier key."""
    from grantflow.api.auth import _tier_export_limit

    plaintext = make_key(patched_session_factory, tier="growth", key_suffix="_tel_growth")
    result = _tier_export_limit(plaintext)
    assert result == "10000/day"
