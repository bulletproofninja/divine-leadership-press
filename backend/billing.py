"""
Subscription billing & affiliate commission ledger for Divine Leadership Press.

Design notes
------------
- Plans are defined server-side ONLY (security: never accept amount from frontend).
- We use the Emergent Stripe Checkout wrapper, which creates one-time payment
  sessions. To model a monthly subscription, each successful payment extends
  the user's `pro_until` timestamp by 30 days. The user re-purchases each
  month. When the owner switches to a live Stripe account with Stripe
  Subscriptions, this layer can be replaced without touching the rest of the app.
- Commission rules (loaded live from affiliate_settings):
    * Signup commission: applied on a referee's FIRST successful paid payment.
    * MRR commission: applied on every subsequent successful payment, but only
      if the referee is still within `active_days_required` days of the original
      signup (default 60).
- Collections introduced here:
    * payment_transactions: ledger of every Stripe Checkout session.
    * subscriptions: one document per user with current plan + expiry.
    * commissions: one document per accrued commission row.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import uuid


# ---- Plan catalog (single source of truth) ----------------------------------
PLANS: Dict[str, Dict] = {
    "author_pro": {
        "id": "author_pro",
        "name": "Author Pro",
        "amount": 19.00,
        "currency": "usd",
        "period_days": 30,
        "tagline": "Everything an indie author needs to publish their book.",
        "features": [
            "Unlimited manuscripts & versions",
            "Full Editor's Desk copy-edit pass",
            "AI editorial polish (tighten, clarify, blurbs)",
            "PDF export at all 12 KDP trim sizes + ePub",
            "OpenAI HD audiobook generation",
            "ElevenLabs narration (bring-your-own key)",
            "Voice memos & dictation",
            "Affiliate program access (30% / 10%)",
        ],
    },
    "estate": {
        "id": "estate",
        "name": "Estate",
        "amount": 49.00,
        "currency": "usd",
        "period_days": 30,
        "tagline": "For publishers, ghostwriters, and multi-author estates.",
        "features": [
            "Everything in Author Pro",
            "Priority Claude / OpenAI quotas",
            "Bulk per-chapter audiobook export",
            "Higher payout priority + perks",
            "Early access to new features",
        ],
    },
}


def get_plan(plan_id: str) -> Optional[Dict]:
    return PLANS.get(plan_id)


def list_plans_public() -> List[Dict]:
    """Public-facing plan list (omit nothing — there are no secrets here)."""
    return list(PLANS.values())


# ---- Transaction record helpers --------------------------------------------
def new_transaction_record(
    *,
    session_id: str,
    user_id: str,
    email: str,
    plan_id: str,
    amount: float,
    currency: str,
    metadata: Optional[Dict] = None,
) -> Dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_id": user_id,
        "email": email,
        "plan_id": plan_id,
        "amount": amount,
        "currency": currency,
        "status": "initiated",         # initiated | complete | expired | failed
        "payment_status": "pending",   # pending | paid | unpaid | no_payment_required
        "metadata": metadata or {},
        "created_at": now,
        "updated_at": now,
        "processed": False,            # flips True once we've credited the subscription
    }


def new_subscription_record(*, user_id: str, plan_id: str, period_days: int) -> Dict:
    now = datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "plan_id": plan_id,
        "active": True,
        "pro_until": (now + timedelta(days=period_days)).isoformat(),
        "first_paid_at": now.isoformat(),
        "last_paid_at": now.isoformat(),
        "payments_count": 1,
        "updated_at": now.isoformat(),
    }


def extend_subscription(existing: Dict, *, plan_id: str, period_days: int) -> Dict:
    """Extend an existing subscription by period_days from the later of
    (now, existing.pro_until). Bumps payments_count and last_paid_at."""
    now = datetime.now(timezone.utc)
    current_until = existing.get("pro_until")
    base = now
    if current_until:
        try:
            parsed = datetime.fromisoformat(current_until)
            if parsed > now:
                base = parsed
        except ValueError:
            pass
    new_until = (base + timedelta(days=period_days)).isoformat()
    return {
        "plan_id": plan_id,
        "active": True,
        "pro_until": new_until,
        "last_paid_at": now.isoformat(),
        "payments_count": int(existing.get("payments_count", 0)) + 1,
        "updated_at": now.isoformat(),
    }


def is_subscription_active(sub: Optional[Dict]) -> bool:
    if not sub or not sub.get("active"):
        return False
    until = sub.get("pro_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > datetime.now(timezone.utc)
    except ValueError:
        return False


# ---- Commission ledger ------------------------------------------------------
def calculate_commission(
    *,
    amount: float,
    is_first_payment: bool,
    settings: Dict,
    referee_signup_at: datetime,
) -> Optional[Dict]:
    """Return a commission dict OR None if no commission is due.

    Rules:
      - settings.enabled must be True.
      - If first payment: amount * signup_commission_percent / 100.
      - Else: amount * mrr_commission_percent / 100, only if referee is still
        within `active_days_required` days of signup.
    """
    if not settings.get("enabled"):
        return None
    if amount <= 0:
        return None

    if is_first_payment:
        pct = float(settings.get("signup_commission_percent", 0))
        kind = "signup"
    else:
        active_days = int(settings.get("active_days_required", 60))
        cutoff = referee_signup_at + timedelta(days=active_days)
        if datetime.now(timezone.utc) > cutoff:
            return None
        pct = float(settings.get("mrr_commission_percent", 0))
        kind = "mrr"

    if pct <= 0:
        return None

    return {
        "kind": kind,
        "percent": pct,
        "amount": round(amount * pct / 100.0, 2),
        "currency": settings.get("currency", "USD"),
    }


def new_commission_record(
    *,
    referrer_user_id: str,
    referee_user_id: str,
    referee_email: str,
    transaction_id: str,
    session_id: str,
    plan_id: str,
    kind: str,
    percent: float,
    amount: float,
    currency: str,
) -> Dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "referrer_user_id": referrer_user_id,
        "referee_user_id": referee_user_id,
        "referee_email": referee_email,
        "transaction_id": transaction_id,
        "session_id": session_id,
        "plan_id": plan_id,
        "kind": kind,                  # signup | mrr
        "percent": percent,
        "amount": amount,
        "currency": currency,
        "status": "pending",           # pending | paid | void
        "paid_at": None,
        "payout_method": None,
        "payout_reference": None,
        "created_at": now,
        "updated_at": now,
    }
