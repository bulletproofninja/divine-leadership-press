# Iteration 14 — Affiliate program: leaderboard + badges + admin settings
import os
import time
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
BASE_URL = BASE_URL.rstrip('/')
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')


def _register(email, name="Tester", password="TestPass123!", referral_code=None):
    payload = {"email": email, "name": name, "password": password}
    if referral_code is not None:
        payload["referral_code"] = referral_code
    return requests.post(f"{API}/auth/register", json=payload, timeout=30)


def _login(email, password="TestPass123!"):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def stamp():
    return int(time.time() * 1000)


# --- Public settings ---

class TestAffiliateSettingsPublic:
    def test_get_settings_default(self):
        r = requests.get(f"{API}/affiliate/settings", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # The defaults — confirm shape and key values per problem statement
        assert body.get("reward_type") == "credits"
        assert body.get("qualifying_event") == "signup"
        assert "commission_percent" in body
        assert isinstance(body["commission_percent"], (int, float))
        # commission_percent default should be 0 (tracking-only) — but may have been
        # mutated by previous super-admin write tests; just verify it's numeric.


# --- Admin: write protection ---

class TestAffiliateAdminAuth:
    def test_put_admin_unauth_401(self):
        r = requests.put(f"{API}/admin/affiliate/settings", json={"reward_type": "credits"}, timeout=15)
        assert r.status_code == 401, r.text

    def test_put_admin_non_super_403(self, stamp):
        r = _register(f"TEST_aff_nonsuper_{stamp}@test.com", name="Plain")
        token = r.json()["token"]
        put = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"reward_type": "credits"},
            headers=_auth(token),
            timeout=15,
        )
        assert put.status_code == 403, put.text
        assert "super" in put.text.lower() or "owner" in put.text.lower()


# --- Admin: super-admin path (flip flag directly in mongo) ---

class TestAffiliateAdminSuper:
    @staticmethod
    async def _flip_super(user_id: str):
        client = AsyncIOMotorClient(MONGO_URL)
        await client[DB_NAME].users.update_one(
            {"id": user_id}, {"$set": {"is_super_admin": True}}
        )
        client.close()

    @staticmethod
    async def _restore_settings(snapshot):
        """Reset the global settings doc to a known snapshot."""
        client = AsyncIOMotorClient(MONGO_URL)
        if snapshot is None:
            await client[DB_NAME].affiliate_settings.delete_one({"_id": "global"})
        else:
            await client[DB_NAME].affiliate_settings.replace_one(
                {"_id": "global"}, snapshot, upsert=True
            )
        client.close()

    @staticmethod
    async def _snapshot_settings():
        client = AsyncIOMotorClient(MONGO_URL)
        doc = await client[DB_NAME].affiliate_settings.find_one({"_id": "global"})
        client.close()
        return doc

    def _make_super(self, stamp, suffix):
        r = _register(f"TEST_aff_super_{suffix}_{stamp}@test.com", name="Owner")
        assert r.status_code == 200
        uid = r.json()["user"]["id"]
        email = r.json()["user"]["email"]
        asyncio.run(self._flip_super(uid))
        # Re-login so JWT loads is_super_admin=true on subsequent /me calls
        lr = _login(email)
        assert lr.status_code == 200
        return lr.json()["token"]

    def test_put_admin_success_and_persists(self, stamp):
        snapshot = asyncio.run(self._snapshot_settings())
        try:
            token = self._make_super(stamp, "ok")
            payload = {
                "reward_type": "cash",
                "commission_percent": 25.0,
                "qualifying_event": "first_paid_subscription",
                "reward_value": 5.0,
                "notes": "Test from iter14",
            }
            put = requests.put(
                f"{API}/admin/affiliate/settings",
                json=payload,
                headers=_auth(token),
                timeout=15,
            )
            assert put.status_code == 200, put.text
            updated = put.json()
            assert updated["reward_type"] == "cash"
            assert updated["commission_percent"] == 25.0
            assert updated["qualifying_event"] == "first_paid_subscription"
            # Public GET reflects the change
            pub = requests.get(f"{API}/affiliate/settings", timeout=15).json()
            assert pub["reward_type"] == "cash"
            assert pub["commission_percent"] == 25.0
            assert pub["qualifying_event"] == "first_paid_subscription"
            assert pub["notes"] == "Test from iter14"
        finally:
            asyncio.run(self._restore_settings(snapshot))

    def test_put_admin_invalid_reward_type_400(self, stamp):
        token = self._make_super(stamp, "badreward")
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"reward_type": "bitcoin"},
            headers=_auth(token),
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_put_admin_invalid_commission_400(self, stamp):
        token = self._make_super(stamp, "badpct")
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"commission_percent": 120},
            headers=_auth(token),
            timeout=15,
        )
        assert r.status_code == 400, r.text
        assert "between 0 and 100" in r.text

    def test_put_admin_invalid_qualifying_event_400(self, stamp):
        token = self._make_super(stamp, "badevt")
        r = requests.put(
            f"{API}/admin/affiliate/settings",
            json={"qualifying_event": "click"},
            headers=_auth(token),
            timeout=15,
        )
        assert r.status_code == 400, r.text


# --- Leaderboard ---

class TestLeaderboard:
    def test_leaderboard_public(self):
        r = requests.get(f"{API}/referrals/leaderboard", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "leaderboard" in body
        assert isinstance(body["leaderboard"], list)

    def test_leaderboard_limit_clamped(self):
        # limit too small clamps to 1
        r = requests.get(f"{API}/referrals/leaderboard?limit=0", timeout=15)
        assert r.status_code == 200
        assert len(r.json()["leaderboard"]) <= 1
        # limit too large clamps to 50
        r = requests.get(f"{API}/referrals/leaderboard?limit=9999", timeout=15)
        assert r.status_code == 200
        assert len(r.json()["leaderboard"]) <= 50

    def test_leaderboard_sorted_desc_with_names(self, stamp):
        # Alice invites 2, Bob invites 1 → Alice ranks above Bob in some slice
        a = _register(f"TEST_lb_alice_{stamp}@test.com", name="LB_Alice")
        a_code = a.json()["user"]["referral_code"]
        _register(f"TEST_lb_a1_{stamp}@test.com", name="A1", referral_code=a_code)
        _register(f"TEST_lb_a2_{stamp}@test.com", name="A2", referral_code=a_code)

        b = _register(f"TEST_lb_bob_{stamp}@test.com", name="LB_Bob")
        b_code = b.json()["user"]["referral_code"]
        _register(f"TEST_lb_b1_{stamp}@test.com", name="B1", referral_code=b_code)

        r = requests.get(f"{API}/referrals/leaderboard?limit=50", timeout=15).json()
        names = [e["name"] for e in r["leaderboard"]]
        counts = [e["count"] for e in r["leaderboard"]]
        # Should contain LB_Alice and LB_Bob, and counts are sorted desc overall
        assert "LB_Alice" in names
        assert "LB_Bob" in names
        assert counts == sorted(counts, reverse=True)
        # LB_Alice's count >= LB_Bob's
        alice_count = next(e["count"] for e in r["leaderboard"] if e["name"] == "LB_Alice")
        bob_count = next(e["count"] for e in r["leaderboard"] if e["name"] == "LB_Bob")
        assert alice_count >= 2
        assert bob_count >= 1
        assert alice_count >= bob_count
        # entries expose name (not email or code)
        for e in r["leaderboard"]:
            assert "email" not in e
            assert "code" not in e


# --- Badges ---

class TestBadges:
    def test_badge_unauth_401(self):
        r = requests.get(f"{API}/auth/me/badge", timeout=15)
        assert r.status_code == 401

    def test_badge_zero_referrals(self, stamp):
        r = _register(f"TEST_badge_zero_{stamp}@test.com", name="Zero")
        token = r.json()["token"]
        b = requests.get(f"{API}/auth/me/badge", headers=_auth(token), timeout=15)
        assert b.status_code == 200, b.text
        body = b.json()
        assert body["badge"] is None
        assert body["count"] == 0

    def test_badge_ambassador_at_1(self, stamp):
        a = _register(f"TEST_badge_amb_{stamp}@test.com", name="AmbA")
        token = a.json()["token"]
        code = a.json()["user"]["referral_code"]
        # Invite 1
        _register(f"TEST_badge_amb_inv_{stamp}@test.com", name="Inv1", referral_code=code)
        b = requests.get(f"{API}/auth/me/badge", headers=_auth(token), timeout=15)
        assert b.status_code == 200
        body = b.json()
        assert body["count"] == 1
        assert body["badge"]["key"] == "ambassador"
        assert body["badge"]["label"] == "Ambassador"

    def test_badge_advocate_at_5(self, stamp):
        # Register Alice + 5 fake referees via direct mongo insert
        a = _register(f"TEST_badge_adv_{stamp}@test.com", name="AdvA")
        token = a.json()["token"]
        code = a.json()["user"]["referral_code"]

        async def _insert_fakes():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            for i in range(5):
                await db.users.insert_one({
                    "id": f"TEST_fake_adv_{stamp}_{i}",
                    "email": f"TEST_fake_adv_{stamp}_{i}@test.com",
                    "name": f"Fake{i}",
                    "password_hash": "x",
                    "referral_code": f"FAKEAD{stamp % 100:02d}{i:01d}"[:8],
                    "referred_by": code,
                })
            client.close()

        async def _cleanup():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.users.delete_many({"id": {"$regex": f"^TEST_fake_adv_{stamp}_"}})
            client.close()

        try:
            asyncio.run(_insert_fakes())
            b = requests.get(f"{API}/auth/me/badge", headers=_auth(token), timeout=15)
            assert b.status_code == 200
            body = b.json()
            assert body["count"] == 5
            assert body["badge"]["key"] == "advocate"
            assert body["badge"]["label"] == "Author Advocate"
        finally:
            asyncio.run(_cleanup())


# --- Regression smoke ---

class TestRegression:
    def test_register_and_me(self, stamp):
        r = _register(f"TEST_reg_smoke_{stamp}@test.com", name="Smoke")
        assert r.status_code == 200
        token = r.json()["token"]
        m = requests.get(f"{API}/auth/me", headers=_auth(token), timeout=15)
        assert m.status_code == 200
        assert m.json().get("referral_code")

    def test_me_referrals_still_works(self, stamp):
        r = _register(f"TEST_mer_smoke_{stamp}@test.com", name="Smoke2")
        token = r.json()["token"]
        m = requests.get(f"{API}/auth/me/referrals", headers=_auth(token), timeout=15)
        assert m.status_code == 200
        body = m.json()
        assert "referral_code" in body
        assert "total_referred" in body
        assert "recent" in body
