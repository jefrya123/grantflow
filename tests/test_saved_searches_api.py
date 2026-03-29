"""Tests for saved search CRUD endpoints."""

from grantflow.models import SavedSearch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_key(client):
    """Create a fresh API key and return the plaintext string."""
    r = client.post("/api/v1/keys")
    assert r.status_code == 200
    return r.json()["key"]


def _auth(key):
    return {"X-API-Key": key}


_VALID_PAYLOAD = {
    "name": "Climate grants",
    "query": "climate change",
    "agency_code": "EPA",
    "category": "environment",
    "eligible_applicants": '["nonprofits"]',
    "min_award": 10000.0,
    "max_award": 500000.0,
    "alert_email": "user@example.com",
}


# ---------------------------------------------------------------------------
# POST /api/v1/saved-searches — create
# ---------------------------------------------------------------------------


def test_create_saved_search_returns_201(client):
    key = _make_key(client)
    r = client.post("/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key))
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Climate grants"
    assert data["alert_email"] == "user@example.com"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_create_saved_search_requires_auth(client):
    r = client.post("/api/v1/saved-searches", json=_VALID_PAYLOAD)
    assert r.status_code == 401


def test_create_saved_search_invalid_email_returns_422(client):
    key = _make_key(client)
    payload = {**_VALID_PAYLOAD, "alert_email": "not-an-email"}
    r = client.post("/api/v1/saved-searches", json=payload, headers=_auth(key))
    assert r.status_code == 422


def test_create_saved_search_minimal_payload(client):
    """Only name and alert_email are required."""
    key = _make_key(client)
    r = client.post(
        "/api/v1/saved-searches",
        json={"name": "Simple", "alert_email": "a@b.com"},
        headers=_auth(key),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["query"] is None
    assert data["agency_code"] is None


# ---------------------------------------------------------------------------
# GET /api/v1/saved-searches — list
# ---------------------------------------------------------------------------


def test_list_saved_searches_empty(client):
    key = _make_key(client)
    r = client.get("/api/v1/saved-searches", headers=_auth(key))
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_saved_searches_returns_own_searches(client):
    key = _make_key(client)
    client.post("/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key))
    client.post(
        "/api/v1/saved-searches",
        json={**_VALID_PAYLOAD, "name": "Second"},
        headers=_auth(key),
    )
    r = client.get("/api/v1/saved-searches", headers=_auth(key))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_saved_searches_requires_auth(client):
    r = client.get("/api/v1/saved-searches")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/saved-searches/{id} — get one
# ---------------------------------------------------------------------------


def test_get_saved_search_by_id(client):
    key = _make_key(client)
    create_r = client.post(
        "/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key)
    )
    search_id = create_r.json()["id"]
    r = client.get(f"/api/v1/saved-searches/{search_id}", headers=_auth(key))
    assert r.status_code == 200
    assert r.json()["id"] == search_id


def test_get_saved_search_requires_auth(client):
    r = client.get("/api/v1/saved-searches/1")
    assert r.status_code == 401


def test_get_saved_search_not_found_returns_404(client):
    key = _make_key(client)
    r = client.get("/api/v1/saved-searches/99999", headers=_auth(key))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/saved-searches/{id} — update
# ---------------------------------------------------------------------------


def test_patch_saved_search_updates_name(client):
    key = _make_key(client)
    create_r = client.post(
        "/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key)
    )
    search_id = create_r.json()["id"]
    r = client.patch(
        f"/api/v1/saved-searches/{search_id}",
        json={"name": "Updated Name"},
        headers=_auth(key),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"
    # Other fields unchanged
    assert r.json()["alert_email"] == "user@example.com"


def test_patch_saved_search_requires_auth(client):
    r = client.patch("/api/v1/saved-searches/1", json={"name": "x"})
    assert r.status_code == 401


def test_patch_saved_search_not_found_returns_404(client):
    key = _make_key(client)
    r = client.patch(
        "/api/v1/saved-searches/99999", json={"name": "x"}, headers=_auth(key)
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/saved-searches/{id} — soft-delete
# ---------------------------------------------------------------------------


def test_delete_saved_search_soft_deletes(client, db_session):
    key = _make_key(client)
    create_r = client.post(
        "/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key)
    )
    search_id = create_r.json()["id"]
    r = client.delete(f"/api/v1/saved-searches/{search_id}", headers=_auth(key))
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    # Confirm is_active=False in DB
    row = db_session.get(SavedSearch, search_id)
    assert row.is_active is False


def test_delete_requires_auth(client):
    r = client.delete("/api/v1/saved-searches/1")
    assert r.status_code == 401


def test_delete_not_found_returns_404(client):
    key = _make_key(client)
    r = client.delete("/api/v1/saved-searches/99999", headers=_auth(key))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Isolation — cannot access another key's saved searches
# ---------------------------------------------------------------------------


def test_cannot_get_other_keys_saved_search(client):
    key_a = _make_key(client)
    key_b = _make_key(client)
    create_r = client.post(
        "/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key_a)
    )
    search_id = create_r.json()["id"]
    r = client.get(f"/api/v1/saved-searches/{search_id}", headers=_auth(key_b))
    assert r.status_code == 404


def test_cannot_patch_other_keys_saved_search(client):
    key_a = _make_key(client)
    key_b = _make_key(client)
    create_r = client.post(
        "/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key_a)
    )
    search_id = create_r.json()["id"]
    r = client.patch(
        f"/api/v1/saved-searches/{search_id}",
        json={"name": "hacked"},
        headers=_auth(key_b),
    )
    assert r.status_code == 404


def test_cannot_delete_other_keys_saved_search(client):
    key_a = _make_key(client)
    key_b = _make_key(client)
    create_r = client.post(
        "/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key_a)
    )
    search_id = create_r.json()["id"]
    r = client.delete(f"/api/v1/saved-searches/{search_id}", headers=_auth(key_b))
    assert r.status_code == 404


def test_list_only_returns_own_searches(client):
    key_a = _make_key(client)
    key_b = _make_key(client)
    client.post("/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key_a))
    client.post("/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key_a))
    r = client.get("/api/v1/saved-searches", headers=_auth(key_b))
    assert r.json()["total"] == 0


def test_deleted_search_excluded_from_list(client):
    key = _make_key(client)
    create_r = client.post(
        "/api/v1/saved-searches", json=_VALID_PAYLOAD, headers=_auth(key)
    )
    search_id = create_r.json()["id"]
    client.delete(f"/api/v1/saved-searches/{search_id}", headers=_auth(key))
    r = client.get("/api/v1/saved-searches", headers=_auth(key))
    assert r.json()["total"] == 0
