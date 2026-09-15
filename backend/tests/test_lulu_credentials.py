"""Encrypted super-admin Lulu credential management tests."""
import os
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

from lulu_integration import decrypt_credential, encrypt_credential


BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


def _register(tag: str):
    email = f"TEST_lulu_{tag}_{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        f"{API}/auth/register",
        json={"email": email, "name": "Lulu Integration Test", "password": "LuluSecurity5!"},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _headers(account):
    return {"Authorization": f"Bearer {account['token']}"}


@pytest.fixture
def accounts():
    admin = _register("admin")
    regular = _register("regular")
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        db.users.update_one(
            {"id": admin["user"]["id"]},
            {"$set": {"is_super_admin": True}},
        )
    yield admin, regular
    with MongoClient(MONGO_URL) as client:
        db = client[DB_NAME]
        ids = [admin["user"]["id"], regular["user"]["id"]]
        db.integration_credentials.delete_many({"owner_id": {"$in": ids}})
        db.users.delete_many({"id": {"$in": ids}})


def test_credential_cipher_round_trip():
    plaintext = "lulu-test-secret-value"
    ciphertext = encrypt_credential(plaintext)
    assert ciphertext != plaintext
    assert decrypt_credential(ciphertext) == plaintext


def test_lulu_credentials_are_admin_only(accounts):
    _, regular = accounts
    for method, path in (
        ("get", "/admin/integrations/lulu"),
        ("put", "/admin/integrations/lulu"),
        ("post", "/admin/integrations/lulu/test"),
        ("delete", "/admin/integrations/lulu"),
    ):
        kwargs = {"headers": _headers(regular), "timeout": 30}
        if method == "put":
            kwargs["json"] = {
                "environment": "production",
                "client_key": "fake-key",
                "client_secret": "fake-secret-value",
            }
        response = getattr(requests, method)(f"{API}{path}", **kwargs)
        assert response.status_code == 403


def test_save_status_and_clear_never_expose_secrets(accounts):
    admin, _ = accounts
    headers = _headers(admin)
    status = requests.get(f"{API}/admin/integrations/lulu", headers=headers, timeout=30)
    assert status.status_code == 200
    assert status.json()["configured"] is False
    assert status.json()["environment"] == "production"

    client_key = "production-client-key-1234"
    client_secret = "production-client-secret-5678"
    saved = requests.put(
        f"{API}/admin/integrations/lulu",
        headers=headers,
        json={
            "environment": "production",
            "client_key": client_key,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["configured"] is True
    assert body["environment"] == "production"
    assert body["client_key_hint"] == "••••1234"
    assert client_key not in saved.text
    assert client_secret not in saved.text

    with MongoClient(MONGO_URL) as client:
        record = client[DB_NAME].integration_credentials.find_one(
            {"provider": "lulu", "owner_id": admin["user"]["id"]},
            {"_id": 0},
        )
    assert record["client_key_encrypted"] != client_key
    assert record["client_secret_encrypted"] != client_secret
    assert decrypt_credential(record["client_key_encrypted"]) == client_key
    assert decrypt_credential(record["client_secret_encrypted"]) == client_secret

    loaded = requests.get(f"{API}/admin/integrations/lulu", headers=headers, timeout=30)
    assert loaded.status_code == 200
    assert "client_key_encrypted" not in loaded.text
    assert "client_secret_encrypted" not in loaded.text
    assert client_key not in loaded.text
    assert client_secret not in loaded.text

    cleared = requests.delete(f"{API}/admin/integrations/lulu", headers=headers, timeout=30)
    assert cleared.status_code == 200
    assert cleared.json()["configured"] is False


def test_connection_requires_saved_credentials(accounts):
    admin, _ = accounts
    response = requests.post(
        f"{API}/admin/integrations/lulu/test",
        headers=_headers(admin),
        timeout=30,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Save Lulu credentials before testing."