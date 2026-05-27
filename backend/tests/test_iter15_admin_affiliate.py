"""Iteration 15 — Owner account + extended affiliate settings schema + is_super_admin propagation.

Covers:
- Owner login (bagmoneyceo@gmail.com / Surfwall1) returns is_super_admin=True + referral_code
- GET /auth/me on owner token → is_super_admin: True
- Public GET /api/affiliate/settings reflects seeded spec
- PUT /api/admin/affiliate/settings happy + validation paths
- is_super_admin field present on register / login / elevenlabs-set / elevenlabs-clear responses (regression)
"""
import os
import time
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


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    return r


def _register_user(suffix=None):
    suffix = suffix or str(int(time.time() * 1000))
    email = f"TEST_iter15_{suffix}@example.com"
    payload = {"email": email, "password": "TestPass123!", "name": f"Iter15 User {suffix}"}
    r = requests.post(f"{API}/auth/register", json=payload, timeout=20)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    body = r.json()
    return body["token"], body["user"], email


@pytest.fixture(scope="module")
def owner_token():
    r = _login(OWNER_EMAIL, OWNER_PASSWORD)
    assert r.status_code == 200, f"Owner login failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["user"].get("is_super_admin") is True, f"Owner is_super_admin not True: {body}"
    return body["token"]


@pytest.fixture(scope="module")
def snapshot_settings(owner_token):
    """Snapshot current settings before mutation tests, restore after."""
    r = requests.get(f"{API}/affiliate/settings", timeout=15)
    assert r.status_code == 200
    snap = r.json()
    yield snap
    # Restore everything we control
    restore_payload = {
        k: snap.get(k) for k in (
            "enabled", "reward_type", "signup_commission_percent", "mrr_commission_percent",
            "minimum_payout", "qualifying_event", "active_days_required", "payout_method",
            "currency", "stripe_connect_enabled", "perks_description", "notes",
        )
    }
    requests.put(
        f"{API}/admin/affiliate/settings",
        json=restore_payload,
        headers={"Authorization": f"Bearer {owner_token}"},
        timeout=20,
    )


# --- Owner login + /auth/me ---
class TestOwnerLogin:
    def test_owner_login_returns_super_admin_and_referral_code(self):
        r = _login(OWNER_EMAIL, OWNER_PASSWORD)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 10
        u = data["user"]
        assert u["email"] == OWNER_EMAIL
        assert u.get("is_super_admin") is True
        assert isinstance(u.get("referral_code"), str) and len(u["referral_code"]) >= 6

    def test_auth_me_owner_is_super_admin(self, owner_token):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {owner_token}"}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == OWNER_EMAIL
        assert body.get("is_super_admin") is True
        assert "referral_code" in body and body["referral_code"]


# --- is_super_admin regression in all user-response shapes ---
class TestIsSuperAdminFieldPresence:
    def test_register_response_has_is_super_admin(self):
        _, user, _ = _register_user()
        assert "is_super_admin" in user
        assert user["is_super_admin"] is False

    def test_login_response_has_is_super_admin(self):
        token, _, email = _register_user(suffix=f"login_{int(time.time()*1000)}")
        r = _login(email, "TestPass123!")
        assert r.status_code == 200
        u = r.json()["user"]
        assert "is_super_admin" in u and u["is_super_admin"] is False

    def test_elevenlabs_set_and_clear_responses_have_is_super_admin(self):
        token, _, _ = _register_user(suffix=f"el_{int(time.time()*1000)}")
        headers = {"Authorization": f"Bearer {token}"}
        # PUT key (any string accepted by validation? Endpoint stores raw string)
        r = requests.put(f"{API}/auth/me/elevenlabs-key", json={"api_key": "sk_test_dummy_iter15"}, headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "is_super_admin" in body and body["is_super_admin"] is False
        assert body.get("has_elevenlabs_key") is True
        # DELETE
        r = requests.delete(f"{API}/auth/me/elevenlabs-key", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "is_super_admin" in body and body["is_super_admin"] is False
        assert body.get("has_elevenlabs_key") is False


# --- Public seeded settings spec ---
class TestSeededSettings:
    def test_public_settings_match_spec(self):
        r = requests.get(f"{API}/affiliate/settings", timeout=15)
        assert r.status_code == 200
        s = r.json()
        assert s["reward_type"] == "cash_and_perks"
        assert float(s["signup_commission_percent"]) == 30.0
        assert float(s["mrr_commission_percent"]) == 10.0
        assert s["qualifying_event"] == "active_subscription_60d"
        assert int(s["active_days_required"]) == 60
        assert s["payout_method"] == "stripe_connect"
        assert s["stripe_connect_enabled"] is False


# --- Admin PUT happy + validation ---
class TestAdminSettingsMutations:
    def test_put_admin_happy_and_public_reflects(self, owner_token, snapshot_settings):
        new_notes = f"Iter15 note {int(time.time())}"
        payload = {
            "signup_commission_percent": 25.0,
            "notes": new_notes,
            "stripe_connect_enabled": False,
        }
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json=payload,
            headers={"Authorization": f"Bearer {owner_token}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert float(body["signup_commission_percent"]) == 25.0
        assert body["notes"] == new_notes
        # Public GET reflects
        pub = requests.get(f"{API}/affiliate/settings", timeout=15).json()
        assert float(pub["signup_commission_percent"]) == 25.0
        assert pub["notes"] == new_notes

    def test_put_admin_invalid_signup_pct_400(self, owner_token):
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"signup_commission_percent": 150},
            headers={"Authorization": f"Bearer {owner_token}"},
            timeout=15,
        )
        assert r.status_code == 400
        assert "between 0 and 100" in r.text

    def test_put_admin_invalid_reward_type_400(self, owner_token):
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"reward_type": "bogus"},
            headers={"Authorization": f"Bearer {owner_token}"},
            timeout=15,
        )
        assert r.status_code == 400
        assert "reward_type" in r.text

    def test_put_admin_invalid_payout_method_400(self, owner_token):
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"payout_method": "bogus"},
            headers={"Authorization": f"Bearer {owner_token}"},
            timeout=15,
        )
        assert r.status_code == 400
        assert "payout_method" in r.text

    def test_put_admin_invalid_qualifying_event_400(self, owner_token):
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"qualifying_event": "bogus"},
            headers={"Authorization": f"Bearer {owner_token}"},
            timeout=15,
        )
        assert r.status_code == 400
        assert "qualifying_event" in r.text

    def test_put_admin_non_admin_403(self):
        token, _, _ = _register_user(suffix=f"nonadmin_{int(time.time()*1000)}")
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"notes": "shouldfail"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert r.status_code == 403, r.text


# --- Regression: leaderboard + badge endpoints still work ---
class TestRegressionEndpoints:
    def test_leaderboard_public(self):
        r = requests.get(f"{API}/referrals/leaderboard", timeout=15)
        assert r.status_code == 200
        assert "leaderboard" in r.json()

    def test_badge_endpoint_for_owner(self, owner_token):
        r = requests.get(f"{API}/auth/me/badge", headers={"Authorization": f"Bearer {owner_token}"}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "badge" in body and "count" in body
