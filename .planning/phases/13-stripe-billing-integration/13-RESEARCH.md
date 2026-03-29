# Phase 13: Stripe Billing Integration - Research

**Researched:** 2026-03-29
**Domain:** Stripe Python SDK v10+, FastAPI webhook handling, SQLAlchemy/Alembic migrations
**Confidence:** HIGH

## Summary

This phase wires Stripe Checkout (subscription mode) into the existing API key infrastructure. The pattern is straightforward: a checkout session is created server-side and the browser redirects to Stripe's hosted checkout page. After payment, Stripe fires a webhook that creates the API key in the database. The success page retrieves the session from Stripe and reveals the plaintext key exactly once.

The project already has a clean, consistent pattern for all three required layers: FastAPI APIRouter with Pydantic schemas, SQLAlchemy ORM models, and Alembic `add_column` migrations. All three layers follow simple, replicable patterns established in phases 3–9. The Stripe SDK (v11+/v14+) follows an identical import/call style to v10 — the `stripe>=10.0` constraint in CONTEXT.md is satisfied by any version from 10 through 14.

The single non-trivial implementation detail is webhook signature verification: FastAPI must receive the raw request bytes (not parsed JSON) before passing them to `stripe.Webhook.construct_event()`. This requires using `Request.body()` directly rather than a Pydantic body parameter. Idempotency is handled by checking whether a key with a given `stripe_subscription_id` already exists before creating a second one.

**Primary recommendation:** Use pre-created Stripe Price IDs stored in env vars (`STRIPE_PRICE_STARTER_ID`, `STRIPE_PRICE_GROWTH_ID`). Do not use inline `price_data` for subscription mode — inline prices cannot be reused or managed and are archived after creation.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- POST `/api/v1/billing/checkout` with JSON `{"tier": "starter"|"growth"}` body, returns `{"checkout_url": "..."}`
- JS on pricing page redirects to checkout_url (no server redirect)
- Email collected by Stripe during checkout — no pre-collection required
- Success redirect: `/billing/success?session_id={id}`; Cancel redirect: `/pricing`
- On `checkout.session.completed`: create NEW `ApiKey` at the paid tier
- Store `stripe_customer_id` and `stripe_subscription_id` on the `ApiKey` row (new columns)
- On `customer.subscription.deleted` or `invoice.payment_failed`: deactivate the associated key
- Success page fetches session from Stripe, reveals plaintext key exactly once
- New `grantflow/billing/` sub-package: `checkout.py` + `webhook.py`
- API routes in `grantflow/api/billing.py`, included in `app.py`
- Web route for `/billing/success` added to `grantflow/web/routes.py`
- Stripe SDK: `stripe>=10.0`
- Webhook signature verification via `stripe.Webhook.construct_event()`
- Starter: $49/mo, Growth: $149/mo

### Claude's Discretion
- Alembic migration naming and column types
- Error response shapes (follow existing `{"error_code": ..., "message": ...}` pattern)
- Stripe product/price creation strategy (create inline vs pre-created price IDs via env vars)

### Deferred Ideas (OUT OF SCOPE)
- Customer portal for managing subscriptions
- Email delivery of API keys
- Upgrade path for existing free keys
- Promo codes / trial periods
- Webhook retry handling / idempotency keys (Stripe handles retries automatically)
</user_constraints>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| stripe | >=10.0 (current: 11.x–14.x) | Stripe API SDK: checkout sessions, webhook verification | Official Stripe Python SDK; construct_event for HMAC verification |
| fastapi | >=0.115.0 (already installed) | API routing, Request object for raw body | Already in project |
| sqlalchemy | >=2.0 (already installed) | ORM model extension | Already in project |
| alembic | >=1.14 (already installed) | Schema migration for new columns | Already in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | >=1.2.0 (already installed) | Load STRIPE_SECRET_KEY etc. from .env | Already used in config.py |
| pydantic | >=2.0 (already installed) | Request/response schemas | Already used for all schemas |

**Installation:**
```bash
uv add "stripe>=10.0"
```

**Version verification:** Confirmed via PyPI search — stripe Python package is currently at 11.x–14.x. The `>=10.0` constraint covers all current versions. (MEDIUM confidence — PyPI search returned 14.4.0 for the `stripe` package but context7 was not used to verify exact current stable branch; all v10+ use the same API surface for checkout sessions.)

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pre-created Price IDs via env vars | inline `price_data` | Inline prices are archived after creation, cannot be reused or updated; env var price IDs are industry standard |
| Jinja2 success page (existing pattern) | Separate SPA/JS page | Existing templates system already used; no reason to deviate |

---

## Architecture Patterns

### Recommended Project Structure
```
grantflow/
├── billing/
│   ├── __init__.py          # empty or re-exports
│   ├── checkout.py          # create_checkout_session(tier, db) -> str (URL)
│   └── webhook.py           # handle_event(event, db) -> None
├── api/
│   └── billing.py           # APIRouter: POST /checkout, POST /webhook
├── web/
│   └── routes.py            # add GET /billing/success (existing file)
alembic/versions/
└── 0009_add_stripe_columns.py
templates/
└── billing_success.html     # new template
```

### Pattern 1: Router Registration (matches existing app.py)
**What:** Import billing router in app.py alongside keys_router
**When to use:** Always — matches established pattern

```python
# grantflow/app.py — add after existing router imports
from grantflow.api.billing import router as billing_router  # noqa: E402
app.include_router(billing_router)
```

### Pattern 2: Checkout Session Creation
**What:** Server creates a Stripe checkout session with mode=subscription, returns URL
**When to use:** POST /api/v1/billing/checkout handler

```python
# Source: https://docs.stripe.com/api/checkout/sessions/create?lang=python
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

session = stripe.checkout.Session.create(
    mode="subscription",
    line_items=[{
        "price": os.getenv("STRIPE_PRICE_STARTER_ID"),  # pre-created Price ID
        "quantity": 1,
    }],
    success_url="https://example.com/billing/success?session_id={CHECKOUT_SESSION_ID}",
    cancel_url="https://example.com/pricing",
    metadata={"tier": "starter"},                        # preserved in webhook
    subscription_data={"metadata": {"tier": "starter"}}, # also set on subscription
)
return {"checkout_url": session.url}
```

**Note:** `{CHECKOUT_SESSION_ID}` is a Stripe template literal — Stripe replaces it with the actual session ID at redirect time. Do not URL-encode it.

### Pattern 3: Webhook Endpoint — Raw Body Required
**What:** FastAPI endpoint that reads raw bytes for signature verification
**When to use:** POST /api/v1/billing/webhook

```python
# Source: https://docs.stripe.com/webhooks + FastAPI community pattern
from fastapi import APIRouter, Request, HTTPException
import stripe

router = APIRouter(prefix="/api/v1")

@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()          # raw bytes — MUST NOT use Pydantic body param
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error_code": "INVALID_PAYLOAD", "message": "Invalid payload"})
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail={"error_code": "INVALID_SIGNATURE", "message": "Invalid signature"})

    # Route by event type
    if event["type"] == "checkout.session.completed":
        handle_checkout_completed(event["data"]["object"], db)
    elif event["type"] == "customer.subscription.deleted":
        handle_subscription_deleted(event["data"]["object"], db)
    elif event["type"] == "invoice.payment_failed":
        handle_payment_failed(event["data"]["object"], db)

    return {"status": "ok"}
```

### Pattern 4: Webhook Event Payloads
**What:** Key fields accessible from each event type

**checkout.session.completed** — `event["data"]["object"]` is a CheckoutSession:
```python
session = event["data"]["object"]
session["id"]               # checkout session ID (cs_...)
session["customer"]         # Stripe customer ID (cus_...)
session["subscription"]     # Stripe subscription ID (sub_...)
session["customer_email"]   # email entered during checkout (may be None if customer object exists)
session["metadata"]         # {"tier": "starter"} — set at session creation
session["payment_status"]   # "paid"
```

**customer.subscription.deleted** — `event["data"]["object"]` is a Subscription:
```python
sub = event["data"]["object"]
sub["id"]          # subscription ID (sub_...)
sub["customer"]    # customer ID (cus_...)
sub["status"]      # "canceled"
```

**invoice.payment_failed** — `event["data"]["object"]` is an Invoice:
```python
inv = event["data"]["object"]
inv["subscription"]    # subscription ID (sub_...)
inv["customer"]        # customer ID (cus_...)
inv["attempt_count"]   # number of failed attempts
```

### Pattern 5: ApiKey Creation in Webhook (matches keys.py)
**What:** Reuse the same key generation logic from keys.py, now with stripe columns

```python
# Source: adapted from grantflow/api/keys.py (verified in codebase)
import hashlib, secrets
from datetime import datetime, timezone
from grantflow.models import ApiKey

def _create_paid_key(tier: str, stripe_customer_id: str, stripe_subscription_id: str, db) -> str:
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
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
    )
    db.add(api_key)
    db.commit()
    return plaintext_key  # shown once on success page
```

### Pattern 6: Success Page — Retrieve Session from Stripe
**What:** GET /billing/success reads session_id from query param, retrieves from Stripe, renders template
**When to use:** After successful checkout redirect

```python
# Source: https://docs.stripe.com/api/checkout/sessions/retrieve
@router.get("/billing/success")
def billing_success(request: Request, session_id: str):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.InvalidRequestError:
        # Invalid or expired session_id
        raise HTTPException(status_code=404, ...)

    # Look up the ApiKey by stripe_subscription_id
    api_key_row = db.query(ApiKey).filter_by(
        stripe_subscription_id=session["subscription"],
        is_active=True,
    ).first()
    # NOTE: key_prefix is safe to display; plaintext key is NOT stored.
    # The success page shows key_prefix + a "copy your key" note.
    # The actual plaintext key must be stored temporarily — see Pitfall 3.
```

**Critical design decision:** The plaintext key is NOT stored in the DB (per API-01). The success page cannot retrieve it from the DB. Three options:
1. Store plaintext key temporarily in the webhook handler (e.g., a `pending_keys` table keyed by session_id, deleted after one read)
2. Store encrypted in a short-TTL cache (Redis, not available here)
3. **Simplest and most aligned with existing pattern:** The webhook creates the key and stores the plaintext key in a `plaintext_key_once` column that is NULLed/cleared after the success page reads it once

Option 3 is recommended — it requires one extra nullable Text column on `api_keys`, cleared on first read of the success page.

### Pattern 7: Alembic `add_column` Migration (matches 0005_add_canonical_id.py)
**What:** Add columns to existing table with nullable=True for backward compatibility

```python
# File: alembic/versions/0009_add_stripe_columns.py
revision: str = "0009"
down_revision: str = "0008"

def upgrade() -> None:
    op.add_column("api_keys", sa.Column("stripe_customer_id", sa.Text(), nullable=True))
    op.add_column("api_keys", sa.Column("stripe_subscription_id", sa.Text(), nullable=True))
    op.add_column("api_keys", sa.Column("plaintext_key_once", sa.Text(), nullable=True))
    op.create_index("ix_api_keys_stripe_subscription_id", "api_keys", ["stripe_subscription_id"])

def downgrade() -> None:
    op.drop_index("ix_api_keys_stripe_subscription_id", table_name="api_keys")
    op.drop_column("api_keys", "stripe_subscription_id")
    op.drop_column("api_keys", "stripe_customer_id")
    op.drop_column("api_keys", "plaintext_key_once")
```

### Anti-Patterns to Avoid
- **Pydantic body param on webhook endpoint:** Using `body: SomeModel` in the webhook signature causes FastAPI to parse JSON before you can read raw bytes — signature verification will fail. Use `Request` directly.
- **Inline `price_data` for subscriptions:** Inline prices are archived after creation (active=False), cannot be reused or upgraded. Always use pre-created Price IDs.
- **Storing plaintext key beyond one read:** The key must be shown exactly once; clear `plaintext_key_once` immediately after rendering the success template.
- **Returning non-200 on unhandled event types:** Stripe retries on non-2xx. Always return `{"status": "ok"}` for unrecognized events.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC signature verification | Custom HMAC comparison | `stripe.Webhook.construct_event()` | Handles timing-safe comparison, timestamp tolerance, and multi-sig headers |
| Checkout redirect UI | Custom payment form | Stripe Checkout (hosted page) | PCI compliance, SCA handling, mobile optimization |
| Subscription lifecycle state machine | Custom status flags | Stripe subscription status + webhook events | Dunning, grace periods, retry logic all handled by Stripe |

**Key insight:** Stripe Checkout + webhooks handles PCI compliance, SCA (Strong Customer Authentication for EU), retry/dunning logic, and subscription state transitions. Custom implementations of any of these would require months of work.

---

## Common Pitfalls

### Pitfall 1: Raw Body Not Preserved for Webhook Verification
**What goes wrong:** Signature verification fails with `SignatureVerificationError` even with correct secret.
**Why it happens:** Using a Pydantic body parameter (`body: dict`) causes FastAPI to parse and re-serialize the JSON, which may change whitespace or key order, breaking the HMAC.
**How to avoid:** The webhook endpoint must use `payload = await request.body()` and NOT declare a Pydantic body param. Route must be `async def`.
**Warning signs:** 400 errors on all webhook deliveries in the Stripe Dashboard.

### Pitfall 2: `{CHECKOUT_SESSION_ID}` Template Literal
**What goes wrong:** Success page receives `{CHECKOUT_SESSION_ID}` as the literal string instead of the actual session ID.
**Why it happens:** The template literal must appear verbatim in `success_url` — Stripe replaces it at redirect time. If it gets URL-encoded (`%7BCHECKOUT_SESSION_ID%7D`) by Python string formatting, Stripe won't replace it.
**How to avoid:** Pass `success_url` as a string literal with `{CHECKOUT_SESSION_ID}` not inside an f-string. Or use `.format()` only for the base URL, leaving the template literal untouched.
**Warning signs:** `session_id` query param is the literal string `{CHECKOUT_SESSION_ID}` in the URL.

### Pitfall 3: Plaintext Key Unavailable on Success Page
**What goes wrong:** The webhook fires and creates a hashed key. The success page tries to show the user their key but only has the hash.
**Why it happens:** Per API-01, the plaintext key is never stored. The webhook runs before the success page renders. There is no way to re-derive the plaintext from the hash.
**How to avoid:** Use the `plaintext_key_once` column pattern: webhook stores the plaintext temporarily, success page reads it once and sets it to NULL immediately after rendering.
**Warning signs:** Success page shows key_prefix only, user never gets their full key.

### Pitfall 4: Webhook Fires Before DB Transaction Commits
**What goes wrong:** In test environments (or very fast production flows), the webhook can arrive before the `db.commit()` in the checkout handler finishes.
**Why it happens:** Stripe fires webhooks nearly synchronously with payment confirmation.
**How to avoid:** For production this is rarely an issue due to network latency. In tests, always mock `stripe.Webhook.construct_event()` rather than testing real webhook delivery.

### Pitfall 5: Duplicate Key Creation on Webhook Retry
**What goes wrong:** Stripe retries the webhook (network timeout, slow response) and a second API key is created for the same subscription.
**Why it happens:** Stripe retries webhooks on non-2xx responses or timeouts. Even with a 200, rare duplicate events can occur.
**How to avoid:** Before creating the key in `handle_checkout_completed`, check if a key with that `stripe_subscription_id` already exists:
```python
existing = db.query(ApiKey).filter_by(stripe_subscription_id=sub_id).first()
if existing:
    return  # idempotent — already processed
```
**Warning signs:** Multiple active API keys with same `stripe_subscription_id` in the database.

### Pitfall 6: `customer_email` May Be None on checkout.session.completed
**What goes wrong:** `session["customer_email"]` is None even though the customer entered an email.
**Why it happens:** When a returning Stripe customer completes checkout, the email may be on the `Customer` object (`session["customer"]`), not directly on the session. New customers typically have `customer_email` populated.
**How to avoid:** Use `session.get("customer_email") or ""` — the email is not required for the key creation flow (just for display). Don't make the success page fail if it's absent.

---

## Code Examples

### Checkout Request Pydantic Schema
```python
# grantflow/api/billing.py
from pydantic import BaseModel
from typing import Literal

class CheckoutRequest(BaseModel):
    tier: Literal["starter", "growth"]

class CheckoutResponse(BaseModel):
    checkout_url: str
```

### Mocking Stripe in Pytest
```python
# Source: https://til.simonwillison.net/pytest/pytest-stripe-signature
# Pattern 1: monkeypatch stripe.checkout.Session.create
def test_checkout_creates_session(client, monkeypatch):
    mock_session = type("Session", (), {"url": "https://checkout.stripe.com/test"})()
    monkeypatch.setattr("stripe.checkout.Session.create", lambda **kwargs: mock_session)
    resp = client.post("/api/v1/billing/checkout", json={"tier": "starter"})
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"

# Pattern 2: monkeypatch stripe.Webhook.construct_event for webhook tests
def test_webhook_checkout_completed(client, db_session, monkeypatch):
    fake_event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_123",
            "customer": "cus_test_456",
            "subscription": "sub_test_789",
            "customer_email": "user@example.com",
            "metadata": {"tier": "starter"},
            "payment_status": "paid",
        }}
    }
    monkeypatch.setattr(
        "stripe.Webhook.construct_event",
        lambda payload, sig, secret: fake_event
    )
    resp = client.post(
        "/api/v1/billing/webhook",
        content=b'{"type":"checkout.session.completed"}',
        headers={"stripe-signature": "t=123,v1=abc"},
    )
    assert resp.status_code == 200
```

### Pricing Page JS Checkout Button
```javascript
// templates/pricing.html — replaces mailto: anchor
async function startCheckout(tier) {
    const resp = await fetch('/api/v1/billing/checkout', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tier: tier}),
    });
    const data = await resp.json();
    window.location.href = data.checkout_url;
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `stripe.api_key = "sk_..."` module-level assignment | Same pattern still valid in v10+ | N/A | No change needed |
| `stripe.checkout.Session.create(...)` | Same — no deprecation | N/A | Works as-is |
| `stripe.Webhook.construct_event()` | Same — stable API | N/A | Works as-is |
| inline `plan` param (legacy) | `price` param with Price ID | ~2020 | Must use `price`, not `plan` |

**Deprecated/outdated:**
- `stripe.Plan`: Replaced by `stripe.Price`. Never use `plan` in line_items.
- `stripe.Charge.create()` for subscriptions: Use Checkout Sessions instead.

---

## Open Questions

1. **Where to store Stripe Price IDs**
   - What we know: CONTEXT.md leaves this to Claude's discretion; Stripe best practice is env vars
   - What's unclear: Whether to add to `config.py` as module-level vars (like `SAM_GOV_API_KEY`) or read inline with `os.getenv()`
   - Recommendation: Add `STRIPE_PRICE_STARTER_ID` and `STRIPE_PRICE_GROWTH_ID` to `config.py` following the existing `SAM_GOV_API_KEY = os.getenv(...)` pattern

2. **Success page template: new file or extend existing**
   - What we know: All pages use Jinja2 extending `base.html`
   - What's unclear: Whether `billing_success.html` needs special no-cache headers to prevent key exposure on browser back
   - Recommendation: Add `Cache-Control: no-store` response header in the success route handler

3. **Stripe webhook endpoint in Stripe Dashboard**
   - What we know: Needs `STRIPE_WEBHOOK_SECRET` from Dashboard > Developers > Webhooks
   - What's unclear: Whether testing instructions should use Stripe CLI (`stripe listen --forward-to`) or test mode webhook
   - Recommendation: Document both in the plan; Stripe CLI is standard for local dev

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| stripe (PyPI) | All billing code | Not installed | — | Install via `uv add "stripe>=10.0"` |
| STRIPE_SECRET_KEY (env) | checkout.py, webhook.py | Not set | — | Must be set before running; use test key for dev |
| STRIPE_WEBHOOK_SECRET (env) | webhook.py | Not set | — | Required; obtain from Stripe Dashboard or `stripe listen` CLI output |
| STRIPE_PRICE_STARTER_ID (env) | checkout.py | Not set | — | Must be pre-created in Stripe Dashboard (test mode) |
| STRIPE_PRICE_GROWTH_ID (env) | checkout.py | Not set | — | Must be pre-created in Stripe Dashboard (test mode) |
| Stripe CLI | Local webhook dev/test | Not checked | — | Optional; can test webhooks via Stripe Dashboard test events |

**Missing dependencies with no fallback:**
- `stripe` Python package — must be installed before any billing code runs
- `STRIPE_SECRET_KEY` — code will raise at runtime without it

**Missing dependencies with fallback:**
- `STRIPE_WEBHOOK_SECRET` — can be mocked in tests; required only for production webhook verification
- `STRIPE_PRICE_STARTER_ID` / `STRIPE_PRICE_GROWTH_ID` — can be mocked in tests; must exist as real Stripe Price objects before going live

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options] testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/test_billing.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BILL-01 | POST /checkout returns checkout_url | unit | `uv run pytest tests/test_billing.py::test_checkout_returns_url -x` | Wave 0 |
| BILL-02 | POST /checkout rejects unknown tier | unit | `uv run pytest tests/test_billing.py::test_checkout_invalid_tier -x` | Wave 0 |
| BILL-03 | Webhook creates ApiKey on checkout.session.completed | unit | `uv run pytest tests/test_billing.py::test_webhook_creates_key -x` | Wave 0 |
| BILL-04 | Webhook is idempotent (duplicate event ignored) | unit | `uv run pytest tests/test_billing.py::test_webhook_idempotent -x` | Wave 0 |
| BILL-05 | Webhook deactivates key on subscription.deleted | unit | `uv run pytest tests/test_billing.py::test_webhook_cancels_key -x` | Wave 0 |
| BILL-06 | Webhook deactivates key on invoice.payment_failed | unit | `uv run pytest tests/test_billing.py::test_webhook_payment_failed -x` | Wave 0 |
| BILL-07 | Invalid webhook signature returns 400 | unit | `uv run pytest tests/test_billing.py::test_webhook_bad_signature -x` | Wave 0 |
| BILL-08 | Success page renders and reveals key once | unit | `uv run pytest tests/test_billing.py::test_success_page -x` | Wave 0 |
| BILL-09 | Success page clears plaintext_key_once after render | unit | `uv run pytest tests/test_billing.py::test_success_page_clears_key -x` | Wave 0 |
| BILL-10 | Pricing page CTA buttons replaced (no mailto:) | unit | `uv run pytest tests/test_billing.py::test_pricing_page_no_mailto -x` | Wave 0 |
| BILL-11 | Alembic migration adds stripe columns to api_keys | integration | manual — `uv run alembic upgrade head` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_billing.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_billing.py` — all BILL-01 through BILL-10 test cases
- [ ] `alembic/versions/0009_add_stripe_columns.py` — migration file
- [ ] `grantflow/billing/__init__.py`, `checkout.py`, `webhook.py` — new sub-package
- [ ] `grantflow/api/billing.py` — new router
- [ ] `templates/billing_success.html` — new template

*(No existing test infrastructure covers billing — entire test file is Wave 0)*

---

## Sources

### Primary (HIGH confidence)
- [Stripe Create Checkout Session API Reference](https://docs.stripe.com/api/checkout/sessions/create?lang=python) — checkout.Session.create() params, mode=subscription, metadata, success_url template literal
- [Stripe Receive Webhook Events](https://docs.stripe.com/webhooks) — construct_event pattern, FastAPI raw body requirement
- [Stripe Webhook Signature Verification](https://docs.stripe.com/webhooks/signature) — ValueError + SignatureVerificationError handling
- [Stripe Subscriptions Webhook Guide](https://docs.stripe.com/billing/subscriptions/webhooks) — event types and payload fields
- Codebase: `grantflow/api/keys.py` — key creation pattern (verified)
- Codebase: `alembic/versions/0005_add_canonical_id.py` — add_column migration pattern (verified)
- Codebase: `grantflow/config.py` — env var pattern (verified)
- Codebase: `tests/conftest.py` — db_session rollback pattern, client fixture (verified)

### Secondary (MEDIUM confidence)
- [Simon Willison TIL: Mocking Stripe signature checks in pytest](https://til.simonwillison.net/pytest/pytest-stripe-signature) — monkeypatch pattern for construct_event
- [FastAPI Stripe Integration Blog (FastSaaS 2025)](https://www.fast-saas.com/blog/fastapi-stripe-integration/) — async request.body() pattern in FastAPI
- [stripe PyPI / libraries.io](https://libraries.io/pypi/stripe) — version 11.x–14.x current (stripe>=10.0 constraint satisfied)
- [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests) — event.id deduplication pattern

### Tertiary (LOW confidence)
- WebSearch results on `price_data` vs `price` ID tradeoffs — verified against official Stripe pricing docs (MEDIUM)
- WebSearch on `customer.subscription.deleted` payload fields — cross-referenced with stripe-webhooks-guide (MEDIUM)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stripe SDK is well-documented; all other deps already in project
- Architecture: HIGH — patterns directly derived from existing codebase + official Stripe docs
- Pitfalls: HIGH for raw body / idempotency / plaintext key (verified patterns); MEDIUM for customer_email None case (cross-referenced)
- Migration pattern: HIGH — verified against two existing migration files in codebase

**Research date:** 2026-03-29
**Valid until:** 2026-04-29 (Stripe API is stable; stripe-python SDK changes are backwards-compatible within major version)
