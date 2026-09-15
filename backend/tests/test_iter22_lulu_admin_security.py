"""Iteration 22: Lulu admin credential lifecycle + safe error behavior.

# Modules/features covered: admin-only settings, encrypted overwrite semantics, safe OAuth test errors.
"""
import os
import uuid

from dotenv import load_dotenv
from pymongo import MongoClient
import pytest
import requests


load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
load_dotenv('/app/backend/.env.local', override=True)

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


def _register(tag: str) -> dict:
    email = f"TEST_iter22_lulu_{tag}_{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        f"{API}/auth/register",
        json={"email": email, "name": "Iter22 Lulu Test", "password": "LuluUiSecurity6!"},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return {
        "email": email,
        "user_id": payload["user"]["id"],
        "token": payload["token"],
    }


def _headers(account: dict) -> dict:
    return {"Authorization": f"Bearer {account['token']}"}


@pytest.fixture
def lulu_accounts():
    admin = _register("admin")
    regular = _register("regular")
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        db.users.update_one({"id": admin["user_id"]}, {"$set": {"is_super_admin": True}})
    yield admin, regular
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        ids = [admin["user_id"], regular["user_id"]]
        db.integration_credentials.delete_many({"owner_id": {"$in": ids}})
        db.users.delete_many({"id": {"$in": ids}})


def test_lulu_replace_overwrites_and_keeps_single_row(lulu_accounts):
    admin, _ = lulu_accounts
    headers = _headers(admin)

    first_key = "fake-prod-key-1111"
    first_secret = "fake-prod-secret-aaaaaaaa"
    first = requests.put(
        f"{API}/admin/integrations/lulu",
        headers=headers,
        json={"environment": "production", "client_key": first_key, "client_secret": first_secret},
        timeout=30,
    )
    assert first.status_code == 200, first.text

    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        first_doc = db.integration_credentials.find_one(
            {"provider": "lulu", "owner_id": admin["user_id"]},
            {"_id": 0},
        )
        assert first_doc is not None
        first_key_encrypted = first_doc["client_key_encrypted"]
        first_secret_encrypted = first_doc["client_secret_encrypted"]

    second_key = "fake-sandbox-key-9999"
    second_secret = "fake-sandbox-secret-bbbbbbbb"
    second = requests.put(
        f"{API}/admin/integrations/lulu",
        headers=headers,
        json={"environment": "sandbox", "client_key": second_key, "client_secret": second_secret},
        timeout=30,
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["configured"] is True
    assert second_body["environment"] == "sandbox"
    assert second_body["client_key_hint"] == "••••9999"

    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        rows = list(
            db.integration_credentials.find(
                {"provider": "lulu", "owner_id": admin["user_id"]},
                {"_id": 0},
            )
        )
    assert len(rows) == 1
    assert rows[0]["environment"] == "sandbox"
    assert rows[0]["client_key_encrypted"] != first_key_encrypted
    assert rows[0]["client_secret_encrypted"] != first_secret_encrypted

    # Secrets/ciphertext should never return to the browser response body.
    assert second_key not in second.text
    assert second_secret not in second.text
    assert rows[0]["client_key_encrypted"] not in second.text
    assert rows[0]["client_secret_encrypted"] not in second.text


def test_lulu_test_connection_invalid_credentials_is_safe_and_non_leaky(lulu_accounts):
    admin, _ = lulu_accounts
    headers = _headers(admin)
    fake_key = "invalid-lulu-key-1234"
    fake_secret = "invalid-lulu-secret-567890"

    saved = requests.put(
        f"{API}/admin/integrations/lulu",
        headers=headers,
        json={"environment": "production", "client_key": fake_key, "client_secret": fake_secret},
        timeout=30,
    )
    assert saved.status_code == 200, saved.text

    tested = requests.post(
        f"{API}/admin/integrations/lulu/test",
        headers=headers,
        timeout=40,
    )
    assert tested.status_code == 400
    detail = tested.json().get("detail", "")
    assert isinstance(detail, str)
    assert detail != ""

    # Safe error contract: no credential, token, or basic-auth leak.
    response_text = tested.text.lower()
    assert fake_key.lower() not in response_text
    assert fake_secret.lower() not in response_text
    assert "basic " not in response_text
    assert "access_token" not in response_text


def test_lulu_admin_endpoints_reject_regular_user(lulu_accounts):
    _, regular = lulu_accounts
    headers = _headers(regular)

    paths = [
        ("get", "/admin/integrations/lulu", None),
        (
            "put",
            "/admin/integrations/lulu",
            {"environment": "production", "client_key": "fake-key", "client_secret": "fake-secret-value"},
        ),
        ("post", "/admin/integrations/lulu/test", None),
        ("delete", "/admin/integrations/lulu", None),
    ]
    for method, path, payload in paths:
        kwargs = {"headers": headers, "timeout": 30}
        if payload is not None:
            kwargs["json"] = payload
        response = getattr(requests, method)(f"{API}{path}", **kwargs)
        assert response.status_code == 403
