# Iteration 12 — referral / affiliate flows
import os
import time
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from dotenv import load_dotenv

# Load frontend env so REACT_APP_BACKEND_URL is available in pytest context
load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set in /app/frontend/.env"
BASE_URL = BASE_URL.rstrip('/')
API = f"{BASE_URL}/api"

# Local mongo direct access (for backfill verification)
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')


def _register(email, name="Tester", password="TestPass123!", referral_code=None):
    payload = {"email": email, "name": name, "password": password}
    if referral_code is not None:
        payload["referral_code"] = referral_code
    return requests.post(f"{API}/auth/register", json=payload, timeout=30)


def _login(email, password="TestPass123!"):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)


def _me(token):
    return requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)


def _my_referrals(token):
    return requests.get(f"{API}/auth/me/referrals", headers={"Authorization": f"Bearer {token}"}, timeout=30)


@pytest.fixture(scope="module")
def stamp():
    return int(time.time() * 1000)


class TestRegisterReferralCode:
    """1. Each new user gets a referral_code (8 chars uppercase)."""

    def test_register_returns_referral_code(self, stamp):
        email = f"TEST_ref_solo_{stamp}@test.com"
        r = _register(email)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "user" in data and "token" in data
        code = data["user"].get("referral_code")
        assert code, "missing referral_code"
        assert len(code) == 8, f"expected 8 chars, got {len(code)}: {code}"
        assert code == code.upper()
        # Login also returns it
        l = _login(email)
        assert l.status_code == 200
        assert l.json()["user"].get("referral_code") == code

    def test_codes_are_unique(self, stamp):
        codes = set()
        for i in range(5):
            r = _register(f"TEST_ref_unique_{stamp}_{i}@test.com")
            assert r.status_code == 200
            code = r.json()["user"]["referral_code"]
            assert code not in codes
            codes.add(code)


class TestReferralAttribution:
    """2. Valid + invalid referral codes during registration."""

    def test_valid_referral_attributes(self, stamp):
        # Alice
        a = _register(f"TEST_ref_alice_{stamp}@test.com", name="Alice")
        assert a.status_code == 200
        alice = a.json()
        alice_code = alice["user"]["referral_code"]
        alice_token = alice["token"]

        # Bob invited by Alice
        b = _register(f"TEST_ref_bob_{stamp}@test.com", name="Bob", referral_code=alice_code)
        assert b.status_code == 200, b.text

        # Carol invited by Alice (lowercase + spaces — should still resolve)
        c = _register(f"TEST_ref_carol_{stamp}@test.com", name="Carol", referral_code=f"  {alice_code.lower()}  ")
        assert c.status_code == 200, c.text

        # Alice's referrals should show 2
        ref = _my_referrals(alice_token)
        assert ref.status_code == 200, ref.text
        body = ref.json()
        assert body["referral_code"] == alice_code
        assert body["total_referred"] == 2, body
        names = [r["name"] for r in body["recent"]]
        assert "Bob" in names and "Carol" in names
        # Email not exposed
        for r in body["recent"]:
            assert "email" not in r, "email should not be exposed in referrals"
            assert "joined_at" in r

        # newest-first sort
        joined = [r["joined_at"] for r in body["recent"]]
        assert joined == sorted(joined, reverse=True)

    def test_invalid_referral_silent_fallback(self, stamp):
        # Anchor user with known code
        anchor = _register(f"TEST_ref_anchor_{stamp}@test.com", name="Anchor")
        anchor_token = anchor.json()["token"]
        before = _my_referrals(anchor_token).json()["total_referred"]

        # Register a user with a bogus code
        r = _register(f"TEST_ref_fakeinvited_{stamp}@test.com", name="FakeInvited", referral_code="FAKEXXXX")
        assert r.status_code == 200, r.text
        # New user account exists with own code
        assert r.json()["user"]["referral_code"]

        after = _my_referrals(anchor_token).json()["total_referred"]
        assert after == before, "invalid code must not increment anyone's count"


class TestMeReferralsEndpoint:
    def test_unauthenticated_401(self):
        r = requests.get(f"{API}/auth/me/referrals", timeout=15)
        assert r.status_code == 401

    def test_me_includes_referral_code(self, stamp):
        r = _register(f"TEST_ref_meinc_{stamp}@test.com")
        token = r.json()["token"]
        m = _me(token)
        assert m.status_code == 200
        assert m.json().get("referral_code")


class TestLegacyBackfill:
    """3. Backfill for legacy users with no referral_code on the db doc."""

    def test_backfill_on_me(self, stamp):
        # Register, then strip the code from mongo to simulate a legacy account
        email = f"TEST_ref_legacy_{stamp}@test.com"
        r = _register(email, name="Legacy")
        assert r.status_code == 200
        token = r.json()["token"]
        user_id = r.json()["user"]["id"]

        async def _strip_and_check():
            mclient = AsyncIOMotorClient(MONGO_URL)
            db = mclient[DB_NAME]
            await db.users.update_one({"id": user_id}, {"$unset": {"referral_code": ""}})
            doc = await db.users.find_one({"id": user_id}, {"_id": 0, "referral_code": 1})
            assert doc is not None
            assert doc.get("referral_code") in (None, "")
            mclient.close()

        async def _read_after():
            mclient = AsyncIOMotorClient(MONGO_URL)
            db = mclient[DB_NAME]
            doc = await db.users.find_one({"id": user_id}, {"_id": 0, "referral_code": 1})
            mclient.close()
            return doc

        asyncio.run(_strip_and_check())

        # Now hit /auth/me — should backfill
        m = _me(token)
        assert m.status_code == 200
        code = m.json().get("referral_code")
        assert code and len(code) == 8, f"backfill failed: {code}"

        # Verify it was persisted
        doc = asyncio.run(_read_after())
        assert doc and doc.get("referral_code") == code


class TestElevenLabsKeyRegression:
    """4. PUT/DELETE elevenlabs-key still returns referral_code in response."""

    def test_put_delete_elevenlabs_key_includes_referral(self, stamp):
        r = _register(f"TEST_ref_eleven_{stamp}@test.com")
        token = r.json()["token"]
        code = r.json()["user"]["referral_code"]

        put = requests.put(
            f"{API}/auth/me/elevenlabs-key",
            json={"api_key": "x" * 32},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert put.status_code == 200, put.text
        assert put.json().get("referral_code") == code
        assert put.json().get("has_elevenlabs_key") is True

        dele = requests.delete(
            f"{API}/auth/me/elevenlabs-key",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert dele.status_code == 200, dele.text
        assert dele.json().get("referral_code") == code
        assert dele.json().get("has_elevenlabs_key") is False


class TestRegressionDocumentsCreate:
    """Quick regression: doc creation still works."""

    def test_create_doc(self, stamp):
        r = _register(f"TEST_ref_docreg_{stamp}@test.com")
        token = r.json()["token"]
        d = requests.post(
            f"{API}/documents",
            json={"title": "Ref Regression Doc", "content": "<p>Hello</p>"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert d.status_code == 200, d.text
        assert d.json()["title"] == "Ref Regression Doc"
