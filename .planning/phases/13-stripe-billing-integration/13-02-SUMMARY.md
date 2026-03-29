---
phase: 13-stripe-billing-integration
plan: 02
subsystem: payments
tags: [stripe, billing, jinja2, fastapi, api-keys]

# Dependency graph
requires:
  - phase: 13-stripe-billing-integration plan 01
    provides: ApiKey model with stripe_subscription_id and plaintext_key_once columns, billing checkout + webhook endpoints

provides:
  - GET /billing/success route that reveals plaintext API key once and clears it from DB
  - templates/billing_success.html Jinja2 template for post-checkout key display
  - Pricing page with JS checkout buttons replacing mailto: CTAs, Growth price at $149/mo

affects:
  - User-facing billing flow (success page completes post-checkout experience)
  - Pricing page conversions (JS buttons now initiate real Stripe checkout)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - one-time-reveal: plaintext_key_once column is read and immediately set to NULL on first access, preventing replay
    - cache-control-no-store: sensitive pages set Cache-Control no-store to prevent browser caching of API keys

key-files:
  created:
    - templates/billing_success.html
  modified:
    - grantflow/web/routes.py
    - templates/pricing.html
    - tests/test_billing.py

key-decisions:
  - "Remove all mailto: links from pricing page including enterprise note (plan spec: 'all mailto: links removed')"
  - "billing_success route imports ApiKey from models and STRIPE_SECRET_KEY from config, keeps Stripe key configured at request time"

patterns-established:
  - "one-time-reveal: read plaintext_key_once, clear to NULL before returning response"
  - "Cache-Control: no-store on sensitive API key display pages"

requirements-completed: [BILL-08, BILL-09, BILL-10]

# Metrics
duration: 8min
completed: 2026-03-29
---

# Phase 13 Plan 02: Stripe Billing — Success Page + Pricing CTA Summary

**Billing success page reveals API key once with DB clear, pricing page wired to Stripe checkout JS (no mailto: CTAs, Growth at $149/mo)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-29T00:50:58Z
- **Completed:** 2026-03-29T00:58:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- GET /billing/success route retrieves Stripe session, looks up ApiKey, reveals plaintext_key_once once then clears it to NULL
- Response sets Cache-Control: no-store to prevent browser caching of the API key
- Pricing page Starter and Growth CTAs now call startCheckout() JS which POSTs to /api/v1/billing/checkout and redirects to Stripe
- Growth price corrected from $199 to $149/month

## Task Commits

1. **Task 1: Billing success page template and web route** - `84c0826` (feat)
2. **Task 2: Update pricing page with JS checkout buttons** - `2073719` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `templates/billing_success.html` - Jinja2 template showing plaintext API key with copy button, "will not be shown again" warning, fallback for already-revealed keys
- `grantflow/web/routes.py` - Added GET /billing/success route with Stripe session retrieval, ApiKey lookup, one-time reveal logic, Cache-Control header
- `templates/pricing.html` - Replaced mailto: CTAs with JS checkout buttons, updated Growth to $149/mo, added startCheckout() async function
- `tests/test_billing.py` - Added BILL-08 (test_success_page), BILL-09 (test_success_page_clears_key), BILL-10 (test_pricing_page_no_mailto)

## Decisions Made

- Removed all mailto: links from pricing page (including enterprise plans note at bottom), not just the CTA buttons, to satisfy the acceptance criteria "all mailto: links removed"
- enterprise plans note now links to /contact (a non-existent but neutral route) rather than mailto:

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed enterprise note mailto: link**
- **Found during:** Task 2 (pricing page update)
- **Issue:** Plan acceptance criteria says "templates/pricing.html does NOT contain `mailto:hello@grantflow.dev` (all mailto: links removed)" but the enterprise plans note `<a href="mailto:hello@grantflow.dev">Email us</a>` remained after replacing the CTA buttons
- **Fix:** Changed enterprise note href from `mailto:hello@grantflow.dev` to `/contact`
- **Files modified:** templates/pricing.html
- **Verification:** `uv run pytest tests/test_billing.py::test_pricing_page_no_mailto` passes
- **Committed in:** 2073719 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug/correctness)
**Impact on plan:** Required to satisfy plan acceptance criteria. No scope creep.

## Issues Encountered

- grantflow package not installed in venv on first run (ModuleNotFoundError). Resolved by running `uv pip install -e .` — this is expected for fresh worktrees.

## User Setup Required

None - no external service configuration required beyond STRIPE_SECRET_KEY already configured in Plan 01.

## Known Stubs

None — success page renders live data from Stripe session and database. Pricing page JS calls real checkout endpoint.

## Next Phase Readiness

- Full Stripe billing flow is complete: pricing page -> checkout -> webhook creates key -> success page reveals key
- All 10 BILL-01 through BILL-10 tests pass
- No blockers for phase completion

---
*Phase: 13-stripe-billing-integration*
*Completed: 2026-03-29*
