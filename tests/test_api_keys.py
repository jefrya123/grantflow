"""Tests for POST /api/v1/keys endpoint."""

import hashlib


from grantflow.models import ApiKey


def test_create_key_returns_plaintext_key(client):
    """POST /api/v1/keys returns a key starting with 'gf_'."""
    response = client.post("/api/v1/keys")
    assert response.status_code == 200
    data = response.json()
    assert "key" in data
    assert data["key"].startswith("gf_")


def test_create_key_hash_stored_in_db(client, db_session):
    """The returned plaintext key is never stored — only its SHA-256 hash is."""
    response = client.post("/api/v1/keys")
    assert response.status_code == 200
    data = response.json()
    plaintext_key = data["key"]

    expected_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
    row = db_session.query(ApiKey).filter_by(key_hash=expected_hash).first()
    assert row is not None, "SHA-256 hash of plaintext key not found in DB"
    assert plaintext_key not in (row.key_hash,), "Plaintext key must not be stored"


def test_create_key_prefix_matches_first_8_chars(client):
    """key_prefix in response equals the first 8 chars of the plaintext key."""
    response = client.post("/api/v1/keys")
    assert response.status_code == 200
    data = response.json()
    assert data["key_prefix"] == data["key"][:8]


def test_create_key_default_tier_is_free(client):
    """Omitting tier defaults to 'free'."""
    response = client.post("/api/v1/keys")
    assert response.status_code == 200
    assert response.json()["tier"] == "free"


def test_create_key_with_explicit_tier(client):
    """Explicit tier is accepted and returned."""
    response = client.post("/api/v1/keys", json={"tier": "starter"})
    assert response.status_code == 200
    assert response.json()["tier"] == "starter"


def test_create_key_returns_created_at(client):
    """Response includes a created_at ISO8601 timestamp."""
    response = client.post("/api/v1/keys")
    assert response.status_code == 200
    data = response.json()
    assert "created_at" in data
    assert data["created_at"]  # non-empty


def test_two_calls_return_different_keys(client):
    """Two successive calls produce different keys."""
    r1 = client.post("/api/v1/keys")
    r2 = client.post("/api/v1/keys")
    assert r1.json()["key"] != r2.json()["key"]


def test_invalid_tier_returns_422_with_error_code(client):
    """Unknown tier returns 422 with error_code INVALID_TIER."""
    response = client.post("/api/v1/keys", json={"tier": "enterprise"})
    assert response.status_code == 422
    data = response.json()
    # FastAPI wraps detail in {"detail": ...} for HTTPException
    detail = data.get("detail", data)
    assert detail["error_code"] == "INVALID_TIER"
    assert "message" in detail


def test_growth_tier_accepted(client):
    """'growth' tier is accepted."""
    response = client.post("/api/v1/keys", json={"tier": "growth"})
    assert response.status_code == 200
    assert response.json()["tier"] == "growth"
