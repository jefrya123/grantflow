"""Tests for GET /api/v1/feed/daily endpoint."""

import hashlib
import datetime

import pytest

from grantflow.models import ApiKey, Opportunity


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def make_key(db, tier: str = "free") -> str:
    plaintext = f"dailyfeed_testkey_{tier}"
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


def make_opportunity(db, **kwargs) -> Opportunity:
    defaults = dict(
        id="opp-default",
        source="test",
        source_id="src-default",
        title="Test Grant",
        post_date="2020-01-01",
        last_updated="2020-01-01",
    )
    defaults.update(kwargs)
    opp = Opportunity(**defaults)
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


TODAY = "2026-03-29"
YESTERDAY = "2026-03-28"


def test_daily_feed_returns_new_and_updated(client, db_session):
    key = make_key(db_session)

    # new: post_date == today
    make_opportunity(db_session, id="opp-new", source_id="s1",
                     post_date=TODAY, last_updated=TODAY)
    # updated: last_updated == today but post_date is older
    make_opportunity(db_session, id="opp-updated", source_id="s2",
                     post_date=YESTERDAY, last_updated=TODAY)
    # stale: both dates are old
    make_opportunity(db_session, id="opp-stale", source_id="s3",
                     post_date=YESTERDAY, last_updated=YESTERDAY)

    resp = client.get(
        f"/api/v1/feed/daily?date={TODAY}",
        headers={"X-API-Key": key},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == TODAY
    assert data["total_new"] == 1
    assert data["total_updated"] == 1
    new_ids = {o["id"] for o in data["new"]}
    updated_ids = {o["id"] for o in data["updated"]}
    assert "opp-new" in new_ids
    assert "opp-updated" in updated_ids
    assert "opp-stale" not in new_ids
    assert "opp-stale" not in updated_ids


def test_daily_feed_missing_date_returns_422(client, db_session):
    key = make_key(db_session)
    resp = client.get("/api/v1/feed/daily", headers={"X-API-Key": key})
    assert resp.status_code == 422


def test_daily_feed_invalid_date_format_returns_422(client, db_session):
    key = make_key(db_session)
    resp = client.get(
        "/api/v1/feed/daily?date=not-a-date",
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 422


def test_daily_feed_no_api_key_returns_401(client, db_session):
    resp = client.get(f"/api/v1/feed/daily?date={TODAY}")
    assert resp.status_code == 401
