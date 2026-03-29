---
phase: 13
slug: stripe-billing-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini / pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_billing.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_billing.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 0 | stripe-dep | unit | `uv run python -c "import stripe; print(stripe.__version__)"` | ✅ / ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | checkout-session | unit | `uv run pytest tests/test_billing.py::test_create_checkout_session -x -q` | ✅ / ❌ W0 | ⬜ pending |
| 13-01-03 | 01 | 1 | webhook-handler | unit | `uv run pytest tests/test_billing.py::test_webhook_handler -x -q` | ✅ / ❌ W0 | ⬜ pending |
| 13-01-04 | 01 | 2 | billing-routes | integration | `uv run pytest tests/test_billing.py::test_billing_routes -x -q` | ✅ / ❌ W0 | ⬜ pending |
| 13-01-05 | 01 | 2 | key-upgrade | integration | `uv run pytest tests/test_billing.py::test_key_tier_upgrade -x -q` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_billing.py` — stubs for checkout, webhook, route tests
- [ ] `tests/conftest.py` — stripe mock fixtures (if not already present)

*Existing test infrastructure (pytest) covers the framework — Wave 0 only needs test stubs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Stripe checkout redirect | stripe-checkout | Requires live Stripe test mode + browser | Visit /billing/upgrade, click upgrade, verify redirect to Stripe hosted page |
| Webhook receipt from Stripe | stripe-webhook | Requires Stripe CLI or ngrok tunnel | `stripe listen --forward-to localhost:8000/api/v1/billing/webhook` then trigger test event |
| Tier upgrade reflected in API key | key-upgrade-live | Requires real Stripe test event | After webhook, verify GET /api/v1/keys returns updated tier |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
