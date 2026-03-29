"""Stripe checkout session creation."""

import stripe
from grantflow.config import (
    STRIPE_SECRET_KEY,
    STRIPE_PRICE_STARTER_ID,
    STRIPE_PRICE_GROWTH_ID,
)

TIER_PRICE_MAP = {
    "starter": STRIPE_PRICE_STARTER_ID,
    "growth": STRIPE_PRICE_GROWTH_ID,
}


def create_checkout_session(tier: str, base_url: str) -> str:
    """Create Stripe checkout session for given tier. Returns checkout URL."""
    stripe.api_key = STRIPE_SECRET_KEY
    price_id = TIER_PRICE_MAP[tier]  # caller validates tier before calling
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing",
        metadata={"tier": tier},
        subscription_data={"metadata": {"tier": tier}},
    )
    return session.url
