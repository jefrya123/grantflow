"""Tests for billing endpoints — BILL-01 through BILL-10."""

from grantflow.models import ApiKey


# ---------------------------------------------------------------------------
# BILL-01: POST /billing/checkout with valid tier returns checkout_url
# ---------------------------------------------------------------------------
def test_checkout_returns_url(client, monkeypatch):
    class FakeSession:
        url = "https://checkout.stripe.com/test"

    import stripe

    monkeypatch.setattr(
        stripe.checkout.Session, "create", lambda **kwargs: FakeSession()
    )
    resp = client.post("/api/v1/billing/checkout", json={"tier": "starter"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["checkout_url"] == "https://checkout.stripe.com/test"


# ---------------------------------------------------------------------------
# BILL-02: POST /billing/checkout with invalid tier returns 422
# ---------------------------------------------------------------------------
def test_checkout_invalid_tier(client):
    resp = client.post("/api/v1/billing/checkout", json={"tier": "invalid"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# BILL-03: Webhook checkout.session.completed creates an ApiKey
# ---------------------------------------------------------------------------
def test_webhook_creates_key(client, db_session, monkeypatch):
    import stripe

    fake_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_test_456",
                "subscription": "sub_test_789",
                "metadata": {"tier": "starter"},
            }
        },
    }
    monkeypatch.setattr(
        stripe.Webhook, "construct_event", lambda payload, sig, secret: fake_event
    )

    resp = client.post(
        "/api/v1/billing/webhook",
        content=b'{"type": "checkout.session.completed"}',
        headers={"stripe-signature": "t=123,v1=abc"},
    )
    assert resp.status_code == 200

    key = (
        db_session.query(ApiKey)
        .filter_by(stripe_subscription_id="sub_test_789")
        .first()
    )
    assert key is not None
    assert key.tier == "starter"
    assert key.is_active is True
    assert key.plaintext_key_once is not None


# ---------------------------------------------------------------------------
# BILL-04: Webhook idempotency — second event with same sub_id skips creation
# ---------------------------------------------------------------------------
def test_webhook_idempotent(client, db_session, monkeypatch):
    import stripe

    fake_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_idem_111",
                "subscription": "sub_idem_222",
                "metadata": {"tier": "starter"},
            }
        },
    }
    monkeypatch.setattr(
        stripe.Webhook, "construct_event", lambda payload, sig, secret: fake_event
    )

    for _ in range(2):
        resp = client.post(
            "/api/v1/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=x"},
        )
        assert resp.status_code == 200

    count = (
        db_session.query(ApiKey)
        .filter_by(stripe_subscription_id="sub_idem_222")
        .count()
    )
    assert count == 1


# ---------------------------------------------------------------------------
# BILL-05: Webhook customer.subscription.deleted deactivates key
# ---------------------------------------------------------------------------
def test_webhook_cancels_key(client, db_session, monkeypatch):
    import hashlib
    import stripe
    from datetime import datetime, timezone

    # Seed an active key
    key = ApiKey(
        key_hash=hashlib.sha256(b"cancel_key").hexdigest(),
        key_prefix="gf_cance",
        tier="starter",
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_count=0,
        stripe_subscription_id="sub_cancel_123",
    )
    db_session.add(key)
    db_session.commit()

    fake_event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_cancel_123"}},
    }
    monkeypatch.setattr(
        stripe.Webhook, "construct_event", lambda payload, sig, secret: fake_event
    )

    resp = client.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=x"},
    )
    assert resp.status_code == 200

    db_session.refresh(key)
    assert key.is_active is False


# ---------------------------------------------------------------------------
# BILL-06: Webhook invoice.payment_failed deactivates key
# ---------------------------------------------------------------------------
def test_webhook_payment_failed(client, db_session, monkeypatch):
    import hashlib
    import stripe
    from datetime import datetime, timezone

    key = ApiKey(
        key_hash=hashlib.sha256(b"fail_key").hexdigest(),
        key_prefix="gf_failk",
        tier="starter",
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_count=0,
        stripe_subscription_id="sub_fail_456",
    )
    db_session.add(key)
    db_session.commit()

    fake_event = {
        "type": "invoice.payment_failed",
        "data": {"object": {"subscription": "sub_fail_456"}},
    }
    monkeypatch.setattr(
        stripe.Webhook, "construct_event", lambda payload, sig, secret: fake_event
    )

    resp = client.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=x"},
    )
    assert resp.status_code == 200

    db_session.refresh(key)
    assert key.is_active is False


# ---------------------------------------------------------------------------
# BILL-07: Webhook with invalid signature returns 400
# ---------------------------------------------------------------------------
def test_webhook_bad_signature(client, monkeypatch):
    import stripe

    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        lambda payload, sig, secret: (_ for _ in ()).throw(
            stripe.SignatureVerificationError("bad sig", "sig")
        ),
    )

    resp = client.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=bad"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# BILL-08: GET /billing/success?session_id=X returns 200 with plaintext key
# ---------------------------------------------------------------------------
def test_success_page(client, db_session, monkeypatch):
    import hashlib
    import stripe
    from datetime import datetime, timezone

    key = ApiKey(
        key_hash=hashlib.sha256(b"success_key_bill08").hexdigest(),
        key_prefix="gf_test_",
        tier="starter",
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_count=0,
        stripe_subscription_id="sub_success_test",
        plaintext_key_once="gf_test_key_abc123",
    )
    db_session.add(key)
    db_session.commit()

    class FakeSession(dict):
        def get(self, k, default=None):
            return {
                "subscription": "sub_success_test",
                "customer_email": "user@example.com",
            }.get(k, default)

    monkeypatch.setattr(
        stripe.checkout.Session, "retrieve", lambda session_id: FakeSession()
    )

    resp = client.get("/billing/success?session_id=cs_test")
    assert resp.status_code == 200
    assert "gf_test_key_abc123" in resp.text
    assert resp.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# BILL-09: After rendering, plaintext_key_once is cleared from the database
# ---------------------------------------------------------------------------
def test_success_page_clears_key(client, db_session, monkeypatch):
    import hashlib
    import stripe
    from datetime import datetime, timezone

    key = ApiKey(
        key_hash=hashlib.sha256(b"success_key_bill09").hexdigest(),
        key_prefix="gf_test2",
        tier="starter",
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_count=0,
        stripe_subscription_id="sub_success_clear",
        plaintext_key_once="gf_test_key_clear999",
    )
    db_session.add(key)
    db_session.commit()

    class FakeSession(dict):
        def get(self, k, default=None):
            return {
                "subscription": "sub_success_clear",
                "customer_email": "user@example.com",
            }.get(k, default)

    monkeypatch.setattr(
        stripe.checkout.Session, "retrieve", lambda session_id: FakeSession()
    )

    # First GET — should show the key
    resp1 = client.get("/billing/success?session_id=cs_clear_test")
    assert resp1.status_code == 200
    assert "gf_test_key_clear999" in resp1.text

    # Verify DB cleared
    db_session.refresh(key)
    assert key.plaintext_key_once is None

    # Second GET — key should not appear (already cleared)
    resp2 = client.get("/billing/success?session_id=cs_clear_test")
    assert resp2.status_code == 200
    assert "gf_test_key_clear999" not in resp2.text


# ---------------------------------------------------------------------------
# BILL-10: Pricing page has no mailto: CTAs and has JS checkout function
# ---------------------------------------------------------------------------
def test_pricing_page_no_mailto(client):
    resp = client.get("/pricing")
    assert resp.status_code == 200
    assert "mailto:" not in resp.text
    assert "startCheckout" in resp.text
    assert "$149" in resp.text
