# Phase 13: Stripe Billing Integration - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire Stripe checkout into the existing API key infrastructure so users can upgrade from free to paid tiers. Replaces the `mailto:` CTAs on the pricing page with real Stripe checkout flows. Does NOT add user accounts — keys are issued per checkout session.

**In scope:**
- Stripe dependency + env vars (STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET)
- `grantflow/billing/` module: checkout session creation + webhook handler
- `POST /api/v1/billing/checkout` — creates Stripe checkout session, returns URL
- `POST /api/v1/billing/webhook` — handles Stripe webhook events
- `GET /billing/success` — success page that reveals the new API key once
- Schema migration: add `stripe_customer_id`, `stripe_subscription_id` to `api_keys`
- Update pricing page: replace `mailto:` CTAs with JS checkout buttons
- Tests for all new code

**Out of scope:**
- User accounts / auth
- Customer portal / subscription management UI
- Trial periods or promo codes
- Email delivery of API keys
- Upgrading existing keys (new key per checkout)

</domain>

<decisions>
## Implementation Decisions

### Checkout Flow
- POST `/api/v1/billing/checkout` with JSON `{"tier": "starter"|"growth"}` body
- Returns `{"checkout_url": "https://checkout.stripe.com/..."}` — JS on pricing page redirects
- Email collected by Stripe during checkout (no pre-collection required)
- Success redirect: `/billing/success?session_id={id}`
- Cancel redirect: `/pricing`

### Tier Upgrade Mechanism
- On `checkout.session.completed` webhook: create a NEW `ApiKey` at the paid tier
- Store `stripe_customer_id` and `stripe_subscription_id` on the `ApiKey` row (new columns)
- On `customer.subscription.deleted` or `invoice.payment_failed`: deactivate the associated key
- Success page fetches session from Stripe, reveals the plaintext key exactly once (must be copied)

### Pricing
- Starter: $49/mo (matches existing pricing page)
- Growth: $149/mo (updated from current $199/mo on pricing page)
- Pricing page: replace `mailto:` CTAs with JS buttons that call POST /api/v1/billing/checkout

### Module Structure
- New `grantflow/billing/` sub-package
  - `grantflow/billing/__init__.py`
  - `grantflow/billing/checkout.py` — `create_checkout_session(tier)` function
  - `grantflow/billing/webhook.py` — webhook event handler
- API routes in `grantflow/api/billing.py` — included in `app.py`
- Web route for `/billing/success` in `grantflow/web/routes.py`
- Stripe SDK: `stripe>=10.0`
- Webhook signature verification via `stripe.Webhook.construct_event()`

### Claude's Discretion
- Alembic migration naming and column types
- Error response shapes (follow existing `{"error_code": ..., "message": ...}` pattern)
- Stripe product/price creation strategy (create inline vs pre-created price IDs via env vars)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `grantflow/models.py` — `ApiKey` model to extend with stripe columns
- `grantflow/api/keys.py` — key creation pattern (hash + prefix + tier + is_active)
- `grantflow/api/auth.py` — `TIER_LIMITS` dict, `_lookup_tier()` pattern
- `grantflow/database.py` — `get_db` dependency, `SessionLocal`
- `tests/conftest.py` — `client` fixture + `db_session` rollback pattern
- `grantflow/api/schemas.py` — Pydantic response models to extend

### Established Patterns
- API routes: `APIRouter(prefix="/api/v1")` — see `keys.py`, `routes.py`
- Web routes: Jinja2 `TemplateResponse` — see `web/routes.py`
- Error shape: `{"error_code": "...", "message": "..."}` via `HTTPException`
- DB: `Depends(get_db)` injection, `db.add()` / `db.commit()`
- Tests: `client.post(...)` with `db_session` override

### Integration Points
- `grantflow/app.py` — include new billing router alongside `keys_router`
- `grantflow/models.py` — add `stripe_customer_id`, `stripe_subscription_id` columns
- `alembic/` — new migration for the two new columns
- `templates/pricing.html` — replace CTA buttons with JS checkout triggers
- `pyproject.toml` — add `stripe>=10.0` dependency

</code_context>

<specifics>
## Specific Ideas

- Use `stripe.checkout.Session.create()` with `mode="subscription"` for recurring billing
- Pass `metadata={"tier": tier}` in checkout session so webhook knows which tier was purchased
- Webhook endpoint must receive raw bytes (not parsed JSON) for signature verification — use `Request.body()` directly
- Success page: use `stripe.checkout.Session.retrieve(session_id)` to get customer email; generate and show key once
- Free key creation remains at `POST /api/v1/keys` (unchanged)

</specifics>

<deferred>
## Deferred Ideas

- Customer portal for managing subscriptions (Stripe customer portal URL generation)
- Email delivery of API keys (SendGrid / SES)
- Upgrade path for existing free keys (would require linking keys to customers)
- Promo codes / trial periods
- Webhook retry handling / idempotency keys (Stripe handles retries automatically)

</deferred>
