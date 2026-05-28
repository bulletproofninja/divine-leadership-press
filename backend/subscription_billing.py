"""
True recurring subscriptions on the owner's Stripe account.

Why a second module? `billing.py` was the one-time-Checkout MVP that used the
platform's shared test key (`STRIPE_API_KEY`) via the emergentintegrations
wrapper. This module talks to the owner's LIVE Stripe account directly with
the raw `stripe` SDK so we can use `mode=subscription` (auto-renewing) and
Customer Portal.

Public surface:
    init_stripe()                          — wire stripe.api_key on import / startup
    is_live_mode() -> bool                 — True if using sk_live_ key
    get_or_create_price(plan_id) -> str    — idempotent Product+Price bootstrap
    create_subscription_checkout(...)      — returns Stripe Checkout Session
    create_portal_session(...)             — returns Customer Portal Session
    verify_webhook(payload, sig, secret)   — verifies a webhook and returns the event

The PLANS catalogue below is the single source of truth for amounts. Amounts
are stored in cents (Stripe convention) — internal billing.py keeps dollars,
this module converts at the boundary.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import stripe

logger = logging.getLogger(__name__)

# Plan catalogue (cents). Keep in lockstep with billing.PLANS dollars.
PLANS_CENTS = {
    "author_pro": {"name": "Author Pro", "amount_cents": 1900, "currency": "usd"},
    "estate":     {"name": "Estate",     "amount_cents": 4900, "currency": "usd"},
}

# In-process cache so we don't search Stripe on every checkout.
_price_id_cache: dict = {}
_initialized = False


def init_stripe() -> None:
    """Configure the stripe SDK with the owner's secret key."""
    global _initialized
    key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not key:
        logger.warning("STRIPE_SECRET_KEY is not set — subscription billing disabled.")
        return
    stripe.api_key = key
    stripe.api_version = "2024-06-20"
    _initialized = True


def is_configured() -> bool:
    return _initialized and bool(stripe.api_key)


def is_live_mode() -> bool:
    return is_configured() and stripe.api_key.startswith("sk_live_")


def assert_configured() -> None:
    if not is_configured():
        raise RuntimeError(
            "Stripe subscription billing is not configured. "
            "Set STRIPE_SECRET_KEY in backend/.env."
        )


def get_or_create_price(plan_id: str) -> str:
    """Idempotently fetch / create a Stripe Product + recurring Price for a plan.

    We tag the Product with `metadata.dlp_plan_id` so we can find it again
    without storing IDs in env vars.
    """
    assert_configured()
    if plan_id in _price_id_cache:
        return _price_id_cache[plan_id]

    plan = PLANS_CENTS.get(plan_id)
    if not plan:
        raise ValueError(f"Unknown plan_id: {plan_id}")

    # 1. Find or create the Product. Use list + filter (immediately consistent)
    # instead of search (eventually consistent) to avoid creating duplicates on
    # rapid retries / cold-cache requests.
    product = None
    try:
        candidates = stripe.Product.list(active=True, limit=100).auto_paging_iter()
        for p in candidates:
            if (p.metadata or {}).get("dlp_plan_id") == plan_id:
                product = p
                break
    except stripe.error.StripeError:
        logger.exception("Stripe Product.list failed for %s — will create", plan_id)

    if product is None:
        product = stripe.Product.create(
            name=f"Divine Leadership Press — {plan['name']}",
            description="Monthly subscription to the Divine Leadership Press publishing suite.",
            metadata={"dlp_plan_id": plan_id, "source": "dlp_autocreate"},
        )

    # 2. Find an active matching recurring Price
    prices = stripe.Price.list(product=product.id, active=True, limit=20).data
    match = next(
        (
            p for p in prices
            if p.unit_amount == plan["amount_cents"]
            and p.currency == plan["currency"]
            and p.recurring
            and p.recurring.interval == "month"
        ),
        None,
    )
    if match is None:
        match = stripe.Price.create(
            product=product.id,
            unit_amount=plan["amount_cents"],
            currency=plan["currency"],
            recurring={"interval": "month"},
            metadata={"dlp_plan_id": plan_id},
        )

    _price_id_cache[plan_id] = match.id
    return match.id


def create_subscription_checkout(
    *,
    user_id: str,
    email: str,
    plan_id: str,
    success_url: str,
    cancel_url: str,
    stripe_customer_id: Optional[str] = None,
    referred_by: Optional[str] = None,
) -> stripe.checkout.Session:
    """Create a `mode=subscription` Checkout Session for the owner's account."""
    assert_configured()
    price_id = get_or_create_price(plan_id)

    metadata = {
        "user_id": user_id,
        "plan_id": plan_id,
        "source": "dlp_subscription",
    }
    if referred_by:
        metadata["referred_by"] = referred_by

    kwargs: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": user_id,
        "metadata": metadata,
        # Critical: the Subscription object on Stripe's side should also carry
        # our metadata, otherwise renewal invoices won't tell us who to credit.
        "subscription_data": {"metadata": metadata},
        "allow_promotion_codes": True,
    }
    if stripe_customer_id:
        kwargs["customer"] = stripe_customer_id
    else:
        kwargs["customer_email"] = email

    return stripe.checkout.Session.create(**kwargs)


def retrieve_checkout_session(session_id: str) -> stripe.checkout.Session:
    assert_configured()
    return stripe.checkout.Session.retrieve(
        session_id,
        expand=["subscription", "customer"],
    )


def create_portal_session(*, stripe_customer_id: str, return_url: str) -> stripe.billing_portal.Session:
    """Stripe-hosted page where the user can update card, cancel, etc."""
    assert_configured()
    return stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=return_url,
    )


def verify_webhook(payload: bytes, sig_header: str, secret: str):
    """Verify a webhook signature and return the parsed event."""
    return stripe.Webhook.construct_event(payload, sig_header, secret)


# ---- Stripe Connect (Express) — affiliate payouts -------------------------
def create_express_account(*, email: str, user_id: str, country: str = "US") -> stripe.Account:
    """Create a connected Express account for an affiliate.

    The owner's platform must have completed Connect onboarding at
    https://dashboard.stripe.com/connect (one-time setup). Until then, this
    call raises stripe.error.InvalidRequestError, which we surface as a 400.
    """
    assert_configured()
    return stripe.Account.create(
        type="express",
        country=country,
        email=email,
        capabilities={
            "transfers": {"requested": True},
        },
        business_type="individual",
        metadata={
            "dlp_user_id": user_id,
            "source": "dlp_affiliate",
        },
    )


def create_onboarding_link(*, account_id: str, refresh_url: str, return_url: str) -> stripe.AccountLink:
    """Generate a single-use Stripe-hosted onboarding URL for the affiliate."""
    assert_configured()
    return stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )


def create_express_login_link(*, account_id: str) -> stripe.LoginLink:
    """Single-sign-on link to the Express dashboard for an affiliate."""
    assert_configured()
    return stripe.Account.create_login_link(account_id)


def retrieve_account_status(account_id: str) -> dict:
    """Lightweight account status for the affiliate's dashboard card."""
    assert_configured()
    acct = stripe.Account.retrieve(account_id)
    requirements = acct.requirements or {}
    return {
        "account_id": acct.id,
        "charges_enabled": bool(acct.charges_enabled),
        "payouts_enabled": bool(acct.payouts_enabled),
        "details_submitted": bool(acct.details_submitted),
        "requirements_due": list(requirements.get("currently_due") or []),
        "disabled_reason": requirements.get("disabled_reason"),
        "email": acct.email,
    }


def create_transfer(
    *,
    amount_cents: int,
    currency: str,
    destination_account_id: str,
    metadata: Optional[dict] = None,
    description: Optional[str] = None,
) -> stripe.Transfer:
    """Transfer funds from the platform balance to a connected account.

    This is the auto-payout mechanism. Funds must be available in the platform
    balance — Stripe holds new subscription payments for ~2-7 days before they
    become available, depending on country.
    """
    assert_configured()
    return stripe.Transfer.create(
        amount=int(amount_cents),
        currency=currency,
        destination=destination_account_id,
        description=description,
        metadata=metadata or {},
    )
