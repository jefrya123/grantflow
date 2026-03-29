"""Billing API router — checkout and webhook endpoints."""

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.orm import Session

from grantflow.database import get_db
from grantflow.config import STRIPE_WEBHOOK_SECRET
from grantflow.billing.checkout import create_checkout_session
from grantflow.billing.webhook import (
    handle_checkout_completed,
    handle_subscription_deleted,
    handle_payment_failed,
)

router = APIRouter(prefix="/api/v1")


class CheckoutRequest(BaseModel):
    tier: Literal["starter", "growth"]


class CheckoutResponse(BaseModel):
    checkout_url: str


@router.post("/billing/checkout", response_model=CheckoutResponse)
def billing_checkout(body: CheckoutRequest, request: Request):
    base_url = str(request.base_url).rstrip("/")
    try:
        url = create_checkout_session(body.tier, base_url)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error_code": "STRIPE_ERROR", "message": str(e)},
        )
    return CheckoutResponse(checkout_url=url)


@router.post("/billing/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "MISSING_SIGNATURE",
                "message": "Missing stripe-signature header",
            },
        )
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_PAYLOAD", "message": "Invalid payload"},
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_SIGNATURE", "message": "Invalid signature"},
        )

    event_type = event["type"]
    event_data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        handle_checkout_completed(event_data, db)
    elif event_type == "customer.subscription.deleted":
        handle_subscription_deleted(event_data, db)
    elif event_type == "invoice.payment_failed":
        handle_payment_failed(event_data, db)

    return {"status": "ok"}
