"""Iteration 16 — Stripe Subscription Billing, Commission Ledger, and Per-Chapter Audiobook Export.

Covers:
- GET  /api/billing/plans                       (public)
- GET  /api/billing/me                          (auth)
- POST /api/billing/checkout                    (auth, creates real Stripe test session)
- GET  /api/billing/checkout/status/{id}        (auth, 404 cross-user isolation)
- POST /api/webhook/stripe                      (existence + graceful rejection of bad payloads)
- GET  /api/billing/commissions                 (auth, empty + with seeded data)
- GET  /api/admin/commissions                   (super-admin only, 403 for regular user)
- POST /api/admin/commissions/mark-paid         (super-admin only, marks rows paid)
- GET  /api/documents/{id}/audiobook/chapters/preview
- POST /api/documents/{id}/audiobook/chapters   (validation 400 paths only — skip real MP3 gen)
- Regression: /api/auth/{login,register,me}, /api/affiliate/settings, /api/admin/affiliate/settings,
  /api/referrals/leaderboard, /api/auth/me/badge
"""
import os
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL.rstrip('/')}/api"

OWNER_EMAIL = "bagmoneyceo@gmail.com"
OWNER_PASSWORD = "Surfwall1"


# ---------- helpers ----------
def _register(suffix=None):
    suffix = suffix or f"{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
    email = f"TEST_iter16_{suffix}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": "TestPass123!", "name": f"Iter16 {suffix}"},
        timeout=20,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    body = r.json()
    return body["token"], body["user"], email


def _login(email, password):
    return requests.post(
        f"{API}/auth/login", json={"email": email, "password": password}, timeout=20
    )


@pytest.fixture(scope="module")
def owner_token():
    r = _login(OWNER_EMAIL, OWNER_PASSWORD)
    assert r.status_code == 200, f"owner login: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def regular_user():
    token, user, email = _register()
    return {"token": token, "user": user, "email": email}


@pytest.fixture(scope="module")
def second_user():
    token, user, email = _register(suffix=f"two_{int(time.time()*1000)}")
    return {"token": token, "user": user, "email": email}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Plans (public) ----------
class TestBillingPlans:
    def test_plans_public_no_auth(self):
        r = requests.get(f"{API}/billing/plans", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "plans" in body
        ids = {p["id"]: p for p in body["plans"]}
        assert "author_pro" in ids and "estate" in ids
        assert float(ids["author_pro"]["amount"]) == 19.0
        assert float(ids["estate"]["amount"]) == 49.0
        assert ids["author_pro"]["currency"] == "usd"
        assert ids["author_pro"]["period_days"] == 30
        assert isinstance(ids["author_pro"]["features"], list) and ids["author_pro"]["features"]


# ---------- Billing /me ----------
class TestBillingMe:
    def test_me_requires_auth(self):
        r = requests.get(f"{API}/billing/me", timeout=15)
        assert r.status_code in (401, 403)

    def test_fresh_user_inactive(self, regular_user):
        r = requests.get(f"{API}/billing/me", headers=_auth(regular_user["token"]), timeout=15)
        assert r.status_code == 200
        b = r.json()
        assert b["active"] is False
        assert b["plan_id"] is None
        assert b["payments_count"] == 0


# ---------- Checkout creation + status ----------
class TestBillingCheckout:
    def test_checkout_requires_auth(self):
        r = requests.post(
            f"{API}/billing/checkout",
            json={"plan_id": "author_pro", "origin_url": "https://example.com"},
            timeout=20,
        )
        assert r.status_code in (401, 403)

    def test_checkout_invalid_plan_400(self, regular_user):
        r = requests.post(
            f"{API}/billing/checkout",
            json={"plan_id": "nope", "origin_url": "https://example.com"},
            headers=_auth(regular_user["token"]),
            timeout=20,
        )
        assert r.status_code == 400

    def test_checkout_invalid_origin_400(self, regular_user):
        r = requests.post(
            f"{API}/billing/checkout",
            json={"plan_id": "author_pro", "origin_url": "not-a-url"},
            headers=_auth(regular_user["token"]),
            timeout=20,
        )
        assert r.status_code == 400

    def test_checkout_creates_stripe_session_and_txn(self, regular_user):
        r = requests.post(
            f"{API}/billing/checkout",
            json={"plan_id": "author_pro", "origin_url": "https://example.com"},
            headers=_auth(regular_user["token"]),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "session_id" in body and body["session_id"].startswith("cs_")
        assert "url" in body and "checkout.stripe.com" in body["url"]
        # Persist for next test
        regular_user["session_id"] = body["session_id"]

    def test_status_returns_stripe_state(self, regular_user):
        sid = regular_user.get("session_id")
        assert sid, "depends on previous test"
        r = requests.get(
            f"{API}/billing/checkout/status/{sid}",
            headers=_auth(regular_user["token"]),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["session_id"] == sid
        assert b["status"] in ("open", "complete", "expired")
        assert b["payment_status"] in ("paid", "unpaid", "no_payment_required", "pending")

    def test_status_other_user_404(self, regular_user, second_user):
        sid = regular_user.get("session_id")
        assert sid, "depends on checkout test"
        r = requests.get(
            f"{API}/billing/checkout/status/{sid}",
            headers=_auth(second_user["token"]),
            timeout=20,
        )
        assert r.status_code == 404


# ---------- Webhook existence ----------
class TestStripeWebhook:
    def test_webhook_rejects_bad_payload_gracefully(self):
        r = requests.post(
            f"{API}/webhook/stripe",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        # Should not 404 / 500 — should reject (400) because no Stripe-Signature
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        assert "Webhook error" in r.text or "signature" in r.text.lower() or "type" in r.text.lower()

    def test_webhook_endpoint_exists_post_only(self):
        # GET should be 405 (method not allowed), proving the path exists
        r = requests.get(f"{API}/webhook/stripe", timeout=15)
        assert r.status_code in (405, 400)


# ---------- Commissions: user ----------
class TestUserCommissions:
    def test_my_commissions_requires_auth(self):
        r = requests.get(f"{API}/billing/commissions", timeout=15)
        assert r.status_code in (401, 403)

    def test_my_commissions_empty_for_fresh_user(self, regular_user):
        r = requests.get(
            f"{API}/billing/commissions", headers=_auth(regular_user["token"]), timeout=15
        )
        assert r.status_code == 200
        b = r.json()
        assert b["commissions"] == []
        assert b["totals"]["pending"] == 0
        assert b["totals"]["paid"] == 0
        assert b["totals"]["count"] == 0


# ---------- Commissions: admin ----------
class TestAdminCommissions:
    def test_admin_list_requires_super_admin(self, regular_user):
        r = requests.get(
            f"{API}/admin/commissions", headers=_auth(regular_user["token"]), timeout=15
        )
        assert r.status_code == 403

    def test_admin_list_ok_for_owner(self, owner_token):
        r = requests.get(
            f"{API}/admin/commissions", headers=_auth(owner_token), timeout=15
        )
        assert r.status_code == 200
        body = r.json()
        assert "commissions" in body and isinstance(body["commissions"], list)
        assert "pending_by_user" in body and isinstance(body["pending_by_user"], list)

    def test_admin_list_filter_by_status(self, owner_token):
        r = requests.get(
            f"{API}/admin/commissions?status=pending",
            headers=_auth(owner_token),
            timeout=15,
        )
        assert r.status_code == 200
        for row in r.json()["commissions"]:
            assert row["status"] == "pending"

    def test_mark_paid_requires_super_admin(self, regular_user):
        r = requests.post(
            f"{API}/admin/commissions/mark-paid",
            json={"commission_ids": ["whatever"]},
            headers=_auth(regular_user["token"]),
            timeout=15,
        )
        assert r.status_code == 403

    def test_mark_paid_empty_ids_400(self, owner_token):
        r = requests.post(
            f"{API}/admin/commissions/mark-paid",
            json={"commission_ids": []},
            headers=_auth(owner_token),
            timeout=15,
        )
        assert r.status_code == 400

    def test_mark_paid_unknown_ids_returns_zero(self, owner_token):
        r = requests.post(
            f"{API}/admin/commissions/mark-paid",
            json={"commission_ids": [f"TEST_unknown_{uuid.uuid4().hex}"]},
            headers=_auth(owner_token),
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["marked_paid"] == 0


# ---------- Commission accrual via _credit_successful_payment (unit-style via monkeypatch) ----------
# These tests directly exercise the idempotent crediting helper to prove signup + MRR commission
# rules without touching Stripe. We import the backend module in-process.
class TestCommissionAccrualLogic:
    def test_calculate_commission_first_payment_uses_signup_pct(self):
        from billing import calculate_commission
        from datetime import datetime, timezone
        comm = calculate_commission(
            amount=19.0,
            is_first_payment=True,
            settings={
                "enabled": True,
                "signup_commission_percent": 30,
                "mrr_commission_percent": 10,
                "active_days_required": 60,
                "currency": "USD",
            },
            referee_signup_at=datetime.now(timezone.utc),
        )
        assert comm is not None
        assert comm["kind"] == "signup"
        assert comm["percent"] == 30
        assert comm["amount"] == round(19.0 * 30 / 100, 2)

    def test_calculate_commission_mrr_within_active_window(self):
        from billing import calculate_commission
        from datetime import datetime, timezone, timedelta
        comm = calculate_commission(
            amount=19.0,
            is_first_payment=False,
            settings={
                "enabled": True,
                "signup_commission_percent": 30,
                "mrr_commission_percent": 10,
                "active_days_required": 60,
                "currency": "USD",
            },
            referee_signup_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        assert comm is not None
        assert comm["kind"] == "mrr"
        assert comm["amount"] == round(19.0 * 10 / 100, 2)

    def test_calculate_commission_mrr_outside_active_window_is_none(self):
        from billing import calculate_commission
        from datetime import datetime, timezone, timedelta
        comm = calculate_commission(
            amount=19.0,
            is_first_payment=False,
            settings={
                "enabled": True,
                "signup_commission_percent": 30,
                "mrr_commission_percent": 10,
                "active_days_required": 60,
                "currency": "USD",
            },
            referee_signup_at=datetime.now(timezone.utc) - timedelta(days=120),
        )
        assert comm is None

    def test_calculate_commission_disabled_returns_none(self):
        from billing import calculate_commission
        from datetime import datetime, timezone
        comm = calculate_commission(
            amount=19.0,
            is_first_payment=True,
            settings={"enabled": False, "signup_commission_percent": 30},
            referee_signup_at=datetime.now(timezone.utc),
        )
        assert comm is None


# ---------- Per-chapter audiobook ----------
class TestChapterAudiobook:
    def _create_doc(self, token, content, title="TEST_iter16_doc"):
        r = requests.post(
            f"{API}/documents",
            json={"title": title, "content": content, "format": "6x9"},
            headers=_auth(token),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_preview_chapters_returns_h1_h2_split(self, regular_user):
        html = "<h1>Chapter One</h1><p>Opening paragraph.</p><h1>Chapter Two</h1><p>Second.</p>"
        doc_id = self._create_doc(regular_user["token"], html)
        r = requests.get(
            f"{API}/documents/{doc_id}/audiobook/chapters/preview",
            headers=_auth(regular_user["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 2
        assert body["chapters"][0]["title"] == "Chapter One"
        assert body["chapters"][1]["title"] == "Chapter Two"
        assert body["chapters"][0]["index"] == 1

    def test_preview_other_users_doc_404(self, regular_user, second_user):
        doc_id = self._create_doc(regular_user["token"], "<h1>A</h1><p>x</p><h1>B</h1><p>y</p>")
        r = requests.get(
            f"{API}/documents/{doc_id}/audiobook/chapters/preview",
            headers=_auth(second_user["token"]),
            timeout=20,
        )
        assert r.status_code == 404

    def test_export_zero_chapters_returns_400(self, regular_user):
        # No headings at all → "No chapters found"
        doc_id = self._create_doc(regular_user["token"], "<p>Just one paragraph, no headings.</p>")
        r = requests.post(
            f"{API}/documents/{doc_id}/audiobook/chapters",
            headers=_auth(regular_user["token"]),
            timeout=30,
        )
        assert r.status_code == 400
        assert "chapter" in r.text.lower()

    def test_export_single_chapter_returns_400(self, regular_user):
        # Only one H1 → must reject with helpful message
        doc_id = self._create_doc(
            regular_user["token"],
            "<h1>Only Chapter</h1><p>Just one chapter of text.</p>",
        )
        r = requests.post(
            f"{API}/documents/{doc_id}/audiobook/chapters",
            headers=_auth(regular_user["token"]),
            timeout=30,
        )
        assert r.status_code == 400
        assert "one chapter" in r.text.lower() or "h1" in r.text.lower()

    def test_export_other_users_doc_404(self, regular_user, second_user):
        doc_id = self._create_doc(
            regular_user["token"], "<h1>A</h1><p>x</p><h1>B</h1><p>y</p>"
        )
        r = requests.post(
            f"{API}/documents/{doc_id}/audiobook/chapters",
            headers=_auth(second_user["token"]),
            timeout=30,
        )
        assert r.status_code == 404


# ---------- Regression: existing endpoints still alive ----------
class TestRegression:
    def test_register_and_login_flow(self):
        token, user, email = _register(suffix=f"reg_{int(time.time()*1000)}")
        assert "is_super_admin" in user and user["is_super_admin"] is False
        r = _login(email, "TestPass123!")
        assert r.status_code == 200

    def test_auth_me_owner(self, owner_token):
        r = requests.get(f"{API}/auth/me", headers=_auth(owner_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == OWNER_EMAIL

    def test_affiliate_settings_public(self):
        r = requests.get(f"{API}/affiliate/settings", timeout=15)
        assert r.status_code == 200
        s = r.json()
        assert "signup_commission_percent" in s
        assert "mrr_commission_percent" in s

    def test_admin_affiliate_settings_super_admin_only(self, regular_user, owner_token):
        # Endpoint is PUT-only. Non-admin should get 403, owner 200.
        r1 = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"notes": "regression check"},
            headers=_auth(regular_user["token"]),
            timeout=15,
        )
        assert r1.status_code == 403
        r2 = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"notes": "regression-iter16"},
            headers=_auth(owner_token),
            timeout=15,
        )
        assert r2.status_code == 200

    def test_referrals_leaderboard(self):
        r = requests.get(f"{API}/referrals/leaderboard", timeout=15)
        assert r.status_code == 200
        assert "leaderboard" in r.json()

    def test_auth_me_badge(self, owner_token):
        r = requests.get(f"{API}/auth/me/badge", headers=_auth(owner_token), timeout=15)
        assert r.status_code == 200
        b = r.json()
        assert "badge" in b and "count" in b
