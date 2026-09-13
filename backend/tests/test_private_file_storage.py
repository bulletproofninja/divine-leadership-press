"""Private object-storage coverage for manuscript sources and generated exports."""
import os
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values


BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
)
assert BASE_URL, "REACT_APP_BACKEND_URL is required"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


def _register(tag: str):
    email = f"TEST_private_files_{tag}_{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        f"{API}/auth/register",
        json={"email": email, "name": "Private Files Test", "password": "Passw0rd!"},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _headers(user):
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture(scope="module")
def owner():
    return _register("owner")


@pytest.fixture(scope="module")
def outsider():
    return _register("outsider")


@pytest.fixture(scope="module")
def uploaded_document(owner):
    source = b"Chapter One\n\nA privately stored manuscript source."
    response = requests.post(
        f"{API}/documents/upload",
        files={"file": ("private-manuscript.txt", source, "text/plain")},
        headers=_headers(owner),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    return {"document": response.json(), "source": source}


def test_uploaded_manuscript_is_registered_and_private(owner, uploaded_document):
    document_id = uploaded_document["document"]["id"]
    response = requests.get(
        f"{API}/documents/{document_id}/files",
        headers=_headers(owner),
        timeout=30,
    )
    assert response.status_code == 200, response.text
    source_files = [item for item in response.json() if item["variant"] == "original"]
    assert len(source_files) == 1
    source_file = source_files[0]
    assert source_file["category"] == "manuscript"
    assert source_file["filename"] == "private-manuscript.txt"
    assert source_file["size_bytes"] == len(uploaded_document["source"])
    assert "storage_path" not in source_file
    assert "user_id" not in source_file

    download = requests.get(
        f"{API}/documents/{document_id}/files/{source_file['id']}",
        headers=_headers(owner),
        timeout=30,
    )
    assert download.status_code == 200
    assert download.content == uploaded_document["source"]
    assert "private" in download.headers.get("cache-control", "").lower() or "no-store" in download.headers.get("cache-control", "").lower()


def test_private_file_routes_require_owner(owner, outsider, uploaded_document):
    document_id = uploaded_document["document"]["id"]
    owner_files = requests.get(
        f"{API}/documents/{document_id}/files",
        headers=_headers(owner),
        timeout=30,
    ).json()
    file_id = owner_files[0]["id"]

    assert requests.get(f"{API}/documents/{document_id}/files", timeout=15).status_code == 401
    assert requests.get(
        f"{API}/documents/{document_id}/files",
        headers=_headers(outsider),
        timeout=15,
    ).status_code == 404
    assert requests.get(
        f"{API}/documents/{document_id}/files/{file_id}",
        headers=_headers(outsider),
        timeout=15,
    ).status_code == 404


def test_pdf_and_epub_exports_are_persisted(owner, uploaded_document):
    document_id = uploaded_document["document"]["id"]
    headers = _headers(owner)

    pdf = requests.post(
        f"{API}/documents/{document_id}/export?format=pdf&trim=6x9",
        headers=headers,
        timeout=90,
    )
    assert pdf.status_code == 200, pdf.text[:300]
    assert pdf.content[:4] == b"%PDF"
    assert pdf.headers.get("x-stored-file-id")

    epub = requests.post(
        f"{API}/documents/{document_id}/export?format=epub",
        headers=headers,
        timeout=90,
    )
    assert epub.status_code == 200, epub.text[:300]
    assert epub.content[:2] == b"PK"
    assert epub.headers.get("x-stored-file-id")

    files = requests.get(
        f"{API}/documents/{document_id}/files",
        headers=headers,
        timeout=30,
    ).json()
    variants = {item["variant"]: item for item in files}
    assert {"original", "pdf:6x9", "epub"}.issubset(variants)

    stored_pdf = requests.get(
        f"{API}/documents/{document_id}/files/{variants['pdf:6x9']['id']}",
        headers=headers,
        timeout=30,
    )
    stored_epub = requests.get(
        f"{API}/documents/{document_id}/files/{variants['epub']['id']}",
        headers=headers,
        timeout=30,
    )
    assert stored_pdf.content[:4] == b"%PDF"
    assert stored_epub.content[:2] == b"PK"


def test_regenerating_same_variant_reuses_private_record(owner, uploaded_document):
    document_id = uploaded_document["document"]["id"]
    headers = _headers(owner)
    before = requests.get(f"{API}/documents/{document_id}/files", headers=headers, timeout=30).json()
    before_pdf = next(item for item in before if item["variant"] == "pdf:6x9")

    time.sleep(0.01)
    response = requests.post(
        f"{API}/documents/{document_id}/export?format=pdf&trim=6x9",
        headers=headers,
        timeout=90,
    )
    assert response.status_code == 200
    assert response.headers.get("x-stored-file-id") == before_pdf["id"]

    after = requests.get(f"{API}/documents/{document_id}/files", headers=headers, timeout=30).json()
    pdf_records = [item for item in after if item["variant"] == "pdf:6x9"]
    assert len(pdf_records) == 1
    assert pdf_records[0]["id"] == before_pdf["id"]