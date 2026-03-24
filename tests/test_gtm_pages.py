"""Tests for GTM web pages: landing, pricing, playground."""
import pytest
from fastapi.testclient import TestClient


def test_landing_page(client: TestClient):
    """GET / returns 200 with GrantFlow branding and link to /pricing."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "GrantFlow" in body
    assert "/pricing" in body


def test_pricing_page(client: TestClient):
    """GET /pricing returns 200 with coverage-based tier names."""
    resp = client.get("/pricing")
    assert resp.status_code == 200
    body = resp.text
    assert "Free" in body
    assert "Starter" in body
    assert "Growth" in body


def test_playground_page(client: TestClient):
    """GET /playground returns 200 (demo key injected or gracefully absent)."""
    resp = client.get("/playground")
    assert resp.status_code == 200
    # Should not be a 500 error page
    assert "Internal Server Error" not in resp.text
    assert "500" not in resp.text or "GrantFlow" in resp.text
