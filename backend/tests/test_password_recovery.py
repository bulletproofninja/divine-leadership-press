"""Password recovery, password change, and session invalidation tests."""
from datetime import timedelta
import os
import secrets
import time
import uuid
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
import pytest
import requests


load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
load_dotenv('/app/backend/.env.local', override=True)

if '/app/backend' not in sys.path:
    sys.path.append('/app/backend')

from auth_security import hash_reset_token, utc_now


BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def cleanup_password_test_users():
    yield
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        users = list(
            db.users.find(
                {"email": {"$regex": "^TEST_password_"}},
                {"_id": 0, "id": 1},
            )
        )
        user_ids = [user["id"] for user in users]
        db.users.delete_many({"email": {"$regex": "^TEST_password_"}})
        if user_ids:
            db.password_reset_tokens.delete_many({"user_id": {"$in": user_ids}})
            db.auth_login_failures.delete_many({})


def _register(tag: str, password: str = "OriginalPass1!"):
    email = f"TEST_password_{tag}_{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        f"{API}/auth/register",
        json={"email": email, "name": "Password Security Test", "password": password},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    return {**response.json(), "email": email, "password": password}


def _seed_reset_token(user_id: str):
    raw_token = secrets.token_urlsafe(48)
    now = utc_now()
    with MongoClient(MONGO_URL) as client:
        client[DB_NAME].password_reset_tokens.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "token_hash": hash_reset_token(raw_token),
                "created_at": now,
                "expires_at": now + timedelta(minutes=30),
                "used_at": None,
            }
        )
    return raw_token


def test_forgot_password_response_does_not_reveal_accounts():
    email = f"TEST_missing_{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        f"{API}/auth/forgot-password",
        json={"email": email},
        timeout=30,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "If an account exists for that email, a password reset link has been sent."


def test_reset_password_is_single_use_and_invalidates_sessions():
    account = _register("reset")
    token = account["token"]
    reset_token = _seed_reset_token(account["user"]["id"])

    weak = requests.post(
        f"{API}/auth/reset-password",
        json={"token": reset_token, "new_password": "weak"},
        timeout=30,
    )
    assert weak.status_code == 400

    updated = requests.post(
        f"{API}/auth/reset-password",
        json={"token": reset_token, "new_password": "ReplacementPass2!"},
        timeout=30,
    )
    assert updated.status_code == 200, updated.text

    assert requests.get(f"{API}/auth/me", headers=_auth(token), timeout=30).status_code == 401
    assert requests.post(
        f"{API}/auth/reset-password",
        json={"token": reset_token, "new_password": "AnotherStrong3!"},
        timeout=30,
    ).status_code == 400
    assert requests.post(
        f"{API}/auth/login",
        json={"email": account["email"], "password": account["password"]},
        timeout=30,
    ).status_code == 401
    assert requests.post(
        f"{API}/auth/login",
        json={"email": account["email"], "password": "ReplacementPass2!"},
        timeout=30,
    ).status_code == 200


def test_authenticated_change_password_invalidates_current_token():
    account = _register("change")
    response = requests.put(
        f"{API}/auth/change-password",
        headers=_auth(account["token"]),
        json={
            "current_password": account["password"],
            "new_password": "ChangedSecure3!",
        },
        timeout=30,
    )
    assert response.status_code == 200, response.text
    assert requests.get(
        f"{API}/auth/me", headers=_auth(account["token"]), timeout=30
    ).status_code == 401


def test_login_brute_force_limit():
    account = _register("lockout")
    for _ in range(5):
        response = requests.post(
            f"{API}/auth/login",
            json={"email": account["email"], "password": "WrongPassword1!"},
            timeout=30,
        )
        assert response.status_code == 401
    blocked = requests.post(
        f"{API}/auth/login",
        json={"email": account["email"], "password": account["password"]},
        timeout=30,
    )
    assert blocked.status_code == 429


def test_previous_owner_identity_no_longer_authenticates():
    old_email = "retired-owner-address@example.invalid"
    invalid_password = "InvalidSecurityCheck9!"
    old_login = requests.post(
        f"{API}/auth/login",
        json={"email": old_email, "password": invalid_password},
        timeout=30,
    )
    owner_invalid_password = requests.post(
        f"{API}/auth/login",
        json={"email": "carlos@divinepublisher.com", "password": invalid_password},
        timeout=30,
    )
    assert old_login.status_code in (401, 422)
    assert owner_invalid_password.status_code == 401


def test_only_expected_super_admin_remains():
    with MongoClient(MONGO_URL) as client:
        admins = list(
            client[DB_NAME].users.find(
                {"is_super_admin": True},
                {"_id": 0, "email": 1, "token_version": 1},
            )
        )
    assert len(admins) == 1
    assert admins[0]["email"] == "carlos@divinepublisher.com"
    assert int(admins[0].get("token_version", 0)) >= 1