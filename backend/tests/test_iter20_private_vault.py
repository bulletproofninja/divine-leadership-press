"""Iteration 20 — private vault backfill + soft-delete coverage for document files."""
import os
import time

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


def _env(name: str, fallback_file: str):
    value = (os.environ.get(name) or "").strip()
    if value:
        return value
    return (dotenv_values(fallback_file).get(name) or "").strip()


BASE_URL = _env("REACT_APP_BACKEND_URL", "/app/frontend/.env").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL is required"
API = f"{BASE_URL}/api"

MONGO_URL = _env("MONGO_URL", "/app/backend/.env")
DB_NAME = _env("DB_NAME", "/app/backend/.env")


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


def _register(tag: str):
    email = f"TEST_iter20_{tag}_{int(time.time() * 1000)}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "name": "Iter20 Tester", "password": "Passw0rd!"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _create_document(token: str, title: str = "TEST Iter20 Vault"):
    r = requests.post(
        f"{API}/documents",
        json={"title": title, "content": "<h1>Chapter 1</h1><p>Some manuscript content for vault checks.</p>"},
        headers=_auth(token),
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _fake_cover_bytes():
    # valid 1x1 PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\xff\xff?\x00\x05"
        b"\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _fake_mp3_bytes():
    return b"ID3\x04\x00\x00" + b"\x00" * 300


def _fake_webm_bytes():
    return b"\x1a\x45\xdf\xa3" + b"\x00\x11\x22\x33" * 256


@pytest.fixture(scope="module")
def owner_user():
    return _register("owner")


def test_private_vault_backfills_cover_upload_and_voice_memo(owner_user):
    token = owner_user["token"]
    doc = _create_document(token)
    doc_id = doc["id"]

    cover = requests.post(
        f"{API}/documents/{doc_id}/cover/upload",
        files={"file": ("iter20-cover.png", _fake_cover_bytes(), "image/png")},
        headers=_auth(token),
        timeout=30,
    )
    assert cover.status_code == 200, cover.text

    audiobook = requests.post(
        f"{API}/documents/{doc_id}/audiobook/upload",
        files={"file": ("iter20-audio.mp3", _fake_mp3_bytes(), "audio/mpeg")},
        headers=_auth(token),
        timeout=30,
    )
    assert audiobook.status_code == 200, audiobook.text

    memo = requests.post(
        f"{API}/documents/{doc_id}/memos?title=Iter20+Memo",
        files={"file": ("iter20-memo.webm", _fake_webm_bytes(), "audio/webm")},
        headers=_auth(token),
        timeout=30,
    )
    assert memo.status_code == 200, memo.text

    files_resp = requests.get(
        f"{API}/documents/{doc_id}/files",
        headers=_auth(token),
        timeout=30,
    )
    assert files_resp.status_code == 200, files_resp.text
    records = files_resp.json()

    variants = {r["variant"]: r for r in records}
    assert "cover" in variants
    assert "uploaded_audiobook" in variants
    memo_rows = [r for r in records if r["variant"].startswith("voice_memo:")]
    assert len(memo_rows) >= 1

    for row in records:
        assert "storage_path" not in row
        assert "user_id" not in row


def test_cover_pdf_export_persists_private_record(owner_user):
    token = owner_user["token"]
    doc = _create_document(token, title="TEST Iter20 Cover PDF")
    doc_id = doc["id"]

    up = requests.post(
        f"{API}/documents/{doc_id}/cover/upload",
        files={"file": ("cover.png", _fake_cover_bytes(), "image/png")},
        headers=_auth(token),
        timeout=30,
    )
    assert up.status_code == 200, up.text

    pdf = requests.post(
        f"{API}/documents/{doc_id}/cover/pdf?trim=6x9",
        headers=_auth(token),
        timeout=60,
    )
    assert pdf.status_code == 200, pdf.text[:300]
    assert pdf.content[:4] == b"%PDF"
    stored_id = pdf.headers.get("x-stored-file-id")
    assert stored_id

    files_resp = requests.get(f"{API}/documents/{doc_id}/files", headers=_auth(token), timeout=30)
    assert files_resp.status_code == 200
    match = [r for r in files_resp.json() if r["variant"] == "cover_pdf:6x9"]
    assert len(match) == 1
    assert match[0]["id"] == stored_id


def test_document_delete_soft_deletes_private_file_records(owner_user):
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME unavailable for method-level soft-delete assertion")

    token = owner_user["token"]
    owner_id = owner_user["user"]["id"]

    upload = requests.post(
        f"{API}/documents/upload",
        files={"file": ("iter20-manuscript.txt", b"alpha\n\nbeta", "text/plain")},
        headers=_auth(token),
        timeout=45,
    )
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["id"]

    pdf = requests.post(
        f"{API}/documents/{doc_id}/export?format=pdf&trim=6x9",
        headers=_auth(token),
        timeout=60,
    )
    assert pdf.status_code == 200, pdf.text[:300]

    delete_resp = requests.delete(f"{API}/documents/{doc_id}", headers=_auth(token), timeout=30)
    assert delete_resp.status_code == 200, delete_resp.text

    with MongoClient(MONGO_URL) as client:
        rows = list(
            client[DB_NAME].document_files.find(
                {"document_id": doc_id, "user_id": owner_id},
                {"_id": 0},
            )
        )

    assert len(rows) >= 2  # original manuscript + pdf export
    assert all(r.get("is_deleted") is True for r in rows)
    assert all(bool(r.get("deleted_at")) for r in rows)
