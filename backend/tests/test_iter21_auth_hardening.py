"""Iteration 21 auth hardening + containment regression tests.

# Modules/features covered: forgot/reset/change password, lockout, token/index security, admin containment.
"""
from datetime import timedelta
import os
import secrets
import sys
import uuid

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


def _register(prefix: str, password: str = "OriginalPass1!") -> dict:
    email = f"TEST_iter21_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        f"{API}/auth/register",
        json={"email": email, "name": "Iter 21 Test User", "password": password},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return {
        "email": email,
        "password": password,
        "token": payload["token"],
        "user_id": payload["user"]["id"],
    }


@pytest.fixture(autouse=True)
def cleanup_test_users():
    yield
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        user_ids = [u.get("id") for u in db.users.find({"email": {"$regex": "^TEST_iter21_"}}, {"_id": 0, "id": 1})]
        db.users.delete_many({"email": {"$regex": "^TEST_iter21_"}})
        if user_ids:
            db.password_reset_tokens.delete_many({"user_id": {"$in": user_ids}})


def test_forgot_password_generic_for_existing_and_unknown_accounts():
    account = _register("forgot_generic")
    existing = requests.post(
        f"{API}/auth/forgot-password", json={"email": account["email"]}, timeout=30
    )
    unknown = requests.post(
        f"{API}/auth/forgot-password",
        json={"email": f"TEST_iter21_missing_{uuid.uuid4().hex[:8]}@example.com"},
        timeout=30,
    )
    assert existing.status_code == 200
    assert unknown.status_code == 200
    assert existing.json() == unknown.json()
    assert "token" not in str(existing.json()).lower()


def test_reset_token_record_stores_only_hash_and_30m_expiry():
    account = _register("token_record")
    response = requests.post(
        f"{API}/auth/forgot-password", json={"email": account["email"]}, timeout=30
    )
    assert response.status_code == 200

    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        token_doc = db.password_reset_tokens.find_one({"user_id": account["user_id"]}, {"_id": 0})
    assert token_doc is not None
    assert isinstance(token_doc.get("token_hash"), str)
    assert token_doc.get("token") is None
    assert token_doc.get("raw_token") is None
    ttl_mins = (token_doc["expires_at"] - token_doc["created_at"]).total_seconds() / 60
    assert 29 <= ttl_mins <= 31


def test_reset_and_rate_limit_ttl_indexes_exist():
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        reset_indexes = list(db.password_reset_tokens.list_indexes())
        reset_req_indexes = list(db.auth_reset_requests.list_indexes())
        login_fail_indexes = list(db.auth_login_failures.list_indexes())

    reset_token_hash = [i for i in reset_indexes if i.get("key", {}).get("token_hash") == 1]
    reset_ttl = [i for i in reset_indexes if i.get("key", {}).get("expires_at") == 1 and i.get("expireAfterSeconds") == 0]
    request_ttl = [i for i in reset_req_indexes if i.get("key", {}).get("expires_at") == 1 and i.get("expireAfterSeconds") == 0]
    login_ttl = [i for i in login_fail_indexes if i.get("key", {}).get("expires_at") == 1 and i.get("expireAfterSeconds") == 0]

    assert len(reset_token_hash) >= 1
    assert len(reset_ttl) >= 1
    assert len(request_ttl) >= 1
    assert len(login_ttl) >= 1


def test_reset_password_rejects_expired_token():
    account = _register("expired")
    raw = secrets.token_urlsafe(48)
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        now = utc_now()
        db.password_reset_tokens.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": account["user_id"],
                "token_hash": hash_reset_token(raw),
                "created_at": now - timedelta(minutes=40),
                "expires_at": now - timedelta(minutes=5),
                "used_at": None,
            }
        )
    response = requests.post(
        f"{API}/auth/reset-password",
        json={"token": raw, "new_password": "ExpiredReject1!"},
        timeout=30,
    )
    assert response.status_code == 400


def test_change_password_requires_current_password():
    account = _register("change_current")
    response = requests.put(
        f"{API}/auth/change-password",
        headers=_auth(account["token"]),
        json={"current_password": "WrongCurrent1!", "new_password": "AnotherStrong2!"},
        timeout=30,
    )
    assert response.status_code == 400
    assert "Current password is incorrect" in response.text


def test_change_password_rejects_same_password():
    account = _register("change_same")
    response = requests.put(
        f"{API}/auth/change-password",
        headers=_auth(account["token"]),
        json={"current_password": account["password"], "new_password": account["password"]},
        timeout=30,
    )
    assert response.status_code == 400
    assert "must be different" in response.text


def test_change_password_invalidates_jwt_and_allows_new_login():
    account = _register("change_invalidate")
    changed = requests.put(
        f"{API}/auth/change-password",
        headers=_auth(account["token"]),
        json={"current_password": account["password"], "new_password": "ChangedAgain9!"},
        timeout=30,
    )
    assert changed.status_code == 200
    assert requests.get(f"{API}/auth/me", headers=_auth(account["token"]), timeout=30).status_code == 401
    old_login = requests.post(
        f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, timeout=30
    )
    new_login = requests.post(
        f"{API}/auth/login", json={"email": account["email"], "password": "ChangedAgain9!"}, timeout=30
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_successful_login_clears_prior_failures():
    account = _register("lockout_clear")
    for _ in range(3):
        wrong = requests.post(
            f"{API}/auth/login", json={"email": account["email"], "password": "WrongPass1!"}, timeout=30
        )
        assert wrong.status_code == 401

    success = requests.post(
        f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, timeout=30
    )
    assert success.status_code == 200

    # If failures were not cleared, the next two wrong attempts would cause early lockout.
    for _ in range(4):
        wrong_after_success = requests.post(
            f"{API}/auth/login", json={"email": account["email"], "password": "WrongPass1!"}, timeout=30
        )
        assert wrong_after_success.status_code == 401


def test_super_admin_containment_and_demotion_of_test_accounts():
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        admins = list(db.users.find({"is_super_admin": True}, {"_id": 0, "email": 1}))
        test_admins = list(
            db.users.find(
                {"is_super_admin": True, "email": {"$regex": "^TEST_"}},
                {"_id": 0, "email": 1},
            )
        )
    assert len(admins) == 1
    assert admins[0]["email"] == "carlos@divinepublisher.com"
    assert test_admins == []


def test_registered_password_uses_bcrypt_2b_format():
    account = _register("bcrypt_check")
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        user = db.users.find_one({"id": account["user_id"]}, {"_id": 0, "password_hash": 1})
    assert isinstance(user.get("password_hash"), str)
    assert user["password_hash"].startswith("$2b$")


def test_login_sets_httponly_cookie():
    account = _register("cookie_check")
    response = requests.post(
        f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, timeout=30
    )
    assert response.status_code == 200
    set_cookie_header = response.headers.get("set-cookie", "")
    # Must be an auth cookie from the application, not infra-only cookies.
    assert "HttpOnly" in set_cookie_header
    assert (
        "access_token=" in set_cookie_header
        or "auth_token=" in set_cookie_header
        or "session=" in set_cookie_header
    )


def test_cors_credentials_do_not_use_wildcard_origin():
    origin = BASE_URL
    response = requests.options(
        f"{API}/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=30,
    )
    assert response.status_code == 200
    allow_origin = response.headers.get("access-control-allow-origin", "")
    allow_credentials = response.headers.get("access-control-allow-credentials", "")
    assert allow_credentials.lower() == "true"
    assert allow_origin != "*"
    assert allow_origin == origin
