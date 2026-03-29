"""Stripe webhook event handlers."""

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from grantflow.models import ApiKey


def handle_checkout_completed(session_data: dict, db: Session) -> None:
    """Create paid ApiKey from checkout.session.completed event."""
    sub_id = session_data["subscription"]
    # Idempotency: skip if key for this subscription already exists
    existing = db.query(ApiKey).filter_by(stripe_subscription_id=sub_id).first()
    if existing:
        return
    tier = session_data.get("metadata", {}).get("tier", "starter")
    customer_id = session_data["customer"]
    plaintext_key = "gf_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
    key_prefix = plaintext_key[:8]
    api_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        tier=tier,
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_count=0,
        stripe_customer_id=customer_id,
        stripe_subscription_id=sub_id,
        plaintext_key_once=plaintext_key,
    )
    db.add(api_key)
    db.commit()


def handle_subscription_deleted(sub_data: dict, db: Session) -> None:
    """Deactivate ApiKey when subscription is canceled."""
    sub_id = sub_data["id"]
    key = (
        db.query(ApiKey)
        .filter_by(stripe_subscription_id=sub_id, is_active=True)
        .first()
    )
    if key:
        key.is_active = False
        db.commit()


def handle_payment_failed(invoice_data: dict, db: Session) -> None:
    """Deactivate ApiKey when payment fails."""
    sub_id = invoice_data.get("subscription")
    if not sub_id:
        return
    key = (
        db.query(ApiKey)
        .filter_by(stripe_subscription_id=sub_id, is_active=True)
        .first()
    )
    if key:
        key.is_active = False
        db.commit()
