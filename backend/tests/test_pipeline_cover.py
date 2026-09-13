"""
Iteration 7 — Pipeline status + Cover image uploads + KDP metadata.

Tests:
- GET /api/documents and /api/documents/{id} include pipeline_status
- pipeline_status booleans correctly reflect content/metadata/cover/pdf/epub/audiobook state
- POST /api/documents/{id}/cover/upload (jpg, exe, empty)
- GET /api/documents/{id}/cover (content-type)
- DELETE /api/documents/{id}/cover
- Cross-user and unauthenticated access
- Export endpoints flip pipeline_status.pdf and pipeline_status.epub
- Audiobook upload flips pipeline_status.audiobook
"""
import os
import time
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


def _ts():
    return str(int(time.time() * 1000))


def _register():
    email = f"TEST_pipe_{_ts()}_{os.getpid()}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "name": "Pipe Test", "password": "P@ssword123"
    })
    assert r.status_code == 200, r.text
    return r.json()["token"], email


@pytest.fixture(scope="module")
def user_a():
    token, email = _register()
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "email": email}


@pytest.fixture(scope="module")
def user_b():
    token, email = _register()
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "email": email}


@pytest.fixture
def fresh_doc(user_a):
    r = requests.post(f"{API}/documents", json={"title": "TEST_Pipeline Book", "content": ""}, headers=user_a["headers"])
    assert r.status_code == 200, r.text
    return r.json()


# ---------- pipeline_status presence ----------

def test_create_doc_has_pipeline_status_all_false(fresh_doc):
    ps = fresh_doc.get("pipeline_status")
    assert ps is not None
    for k in ("manuscript", "metadata", "cover", "pdf", "epub", "audiobook"):
        assert ps[k] is False, f"{k} should be False on fresh doc"
    assert fresh_doc.get("cover_image_ext") is None
    assert fresh_doc.get("last_pdf_export_at") is None
    assert fresh_doc.get("last_epub_export_at") is None
    assert fresh_doc.get("last_audio_export_at") is None


def test_list_docs_includes_pipeline_status(user_a, fresh_doc):
    r = requests.get(f"{API}/documents", headers=user_a["headers"])
    assert r.status_code == 200
    docs = r.json()
    assert len(docs) >= 1
    for d in docs:
        assert "pipeline_status" in d
        ps = d["pipeline_status"]
        assert set(ps.keys()) >= {"manuscript", "metadata", "cover", "pdf", "epub", "audiobook"}


# ---------- manuscript flag ----------

def test_manuscript_false_when_short_content(user_a, fresh_doc):
    r = requests.put(f"{API}/documents/{fresh_doc['id']}",
                     json={"content": "<p>hi</p>"}, headers=user_a["headers"])
    assert r.status_code == 200
    assert r.json()["pipeline_status"]["manuscript"] is False


def test_manuscript_true_when_long_content(user_a, fresh_doc):
    long_text = "A" * 80
    r = requests.put(f"{API}/documents/{fresh_doc['id']}",
                     json={"content": f"<p>{long_text}</p>"}, headers=user_a["headers"])
    assert r.status_code == 200
    assert r.json()["pipeline_status"]["manuscript"] is True


# ---------- metadata flag ----------

def test_metadata_false_when_only_author(user_a, fresh_doc):
    r = requests.put(f"{API}/documents/{fresh_doc['id']}",
                     json={"metadata": {"author": "John Doe"}}, headers=user_a["headers"])
    assert r.status_code == 200
    assert r.json()["pipeline_status"]["metadata"] is False


def test_metadata_false_when_only_description(user_a, fresh_doc):
    r = requests.put(f"{API}/documents/{fresh_doc['id']}",
                     json={"metadata": {"author": "", "description": "A great book"}}, headers=user_a["headers"])
    assert r.status_code == 200
    assert r.json()["pipeline_status"]["metadata"] is False


def test_metadata_true_when_both_set(user_a, fresh_doc):
    r = requests.put(f"{API}/documents/{fresh_doc['id']}",
                     json={"metadata": {"author": "John Doe", "description": "A great book"}},
                     headers=user_a["headers"])
    assert r.status_code == 200
    assert r.json()["pipeline_status"]["metadata"] is True


# ---------- cover endpoints ----------

def _fake_jpg_bytes():
    # >= 64 bytes
    return b"\xff\xd8\xff\xe0" + b"X" * 200 + b"\xff\xd9"


def test_cover_upload_valid_jpg(user_a, fresh_doc):
    files = {"file": ("cover.jpg", _fake_jpg_bytes(), "image/jpeg")}
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/upload",
                      files=files, headers=user_a["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uploaded"] is True
    assert body["extension"] == "jpg"

    # Verify on document
    r2 = requests.get(f"{API}/documents/{fresh_doc['id']}", headers=user_a["headers"])
    assert r2.status_code == 200
    d = r2.json()
    assert d["cover_image_ext"] == "jpg"
    assert d["pipeline_status"]["cover"] is True


def test_cover_upload_unsupported_ext(user_a, fresh_doc):
    files = {"file": ("malware.exe", _fake_jpg_bytes(), "application/octet-stream")}
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/upload",
                      files=files, headers=user_a["headers"])
    assert r.status_code == 400
    assert "image" in r.text.lower() or "unsupported" in r.text.lower()


def test_cover_upload_empty_bytes(user_a, fresh_doc):
    files = {"file": ("cover.jpg", b"", "image/jpeg")}
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/upload",
                      files=files, headers=user_a["headers"])
    assert r.status_code == 400


def test_cover_fetch_returns_image_bytes(user_a, fresh_doc):
    # Upload first
    files = {"file": ("cover.jpg", _fake_jpg_bytes(), "image/jpeg")}
    up = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/upload",
                       files=files, headers=user_a["headers"])
    assert up.status_code == 200
    r = requests.get(f"{API}/documents/{fresh_doc['id']}/cover", headers=user_a["headers"])
    assert r.status_code == 200
    assert r.headers.get("content-type") == "image/jpeg"
    assert len(r.content) >= 64


def test_cover_delete(user_a, fresh_doc):
    files = {"file": ("cover.jpg", _fake_jpg_bytes(), "image/jpeg")}
    requests.post(f"{API}/documents/{fresh_doc['id']}/cover/upload",
                  files=files, headers=user_a["headers"])
    r = requests.delete(f"{API}/documents/{fresh_doc['id']}/cover", headers=user_a["headers"])
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    # Subsequent fetch → 404
    r2 = requests.get(f"{API}/documents/{fresh_doc['id']}/cover", headers=user_a["headers"])
    assert r2.status_code == 404

    # Doc cover_image_ext cleared
    r3 = requests.get(f"{API}/documents/{fresh_doc['id']}", headers=user_a["headers"])
    assert r3.json()["cover_image_ext"] is None
    assert r3.json()["pipeline_status"]["cover"] is False


def test_cover_other_user_404(user_a, user_b, fresh_doc):
    files = {"file": ("cover.jpg", _fake_jpg_bytes(), "image/jpeg")}
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/upload",
                      files=files, headers=user_b["headers"])
    assert r.status_code == 404


def test_cover_unauthenticated(fresh_doc):
    files = {"file": ("cover.jpg", _fake_jpg_bytes(), "image/jpeg")}
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/upload", files=files)
    assert r.status_code == 401


# ---------- export flips pdf / epub ----------

def test_export_pdf_flips_pipeline(user_a):
    # Make a new doc
    r = requests.post(f"{API}/documents", json={"title": "TEST_Export", "content": "<p>" + "X" * 80 + "</p>"},
                      headers=user_a["headers"])
    doc_id = r.json()["id"]
    rx = requests.post(f"{API}/documents/{doc_id}/export?format=pdf&trim=6x9", headers=user_a["headers"])
    assert rx.status_code == 200
    rd = requests.get(f"{API}/documents/{doc_id}", headers=user_a["headers"])
    assert rd.json()["pipeline_status"]["pdf"] is True
    assert rd.json()["last_pdf_export_at"] is not None


def test_export_epub_flips_pipeline(user_a):
    r = requests.post(f"{API}/documents", json={"title": "TEST_Epub", "content": "<p>" + "X" * 80 + "</p>"},
                      headers=user_a["headers"])
    doc_id = r.json()["id"]
    rx = requests.post(f"{API}/documents/{doc_id}/export?format=epub", headers=user_a["headers"])
    assert rx.status_code == 200
    rd = requests.get(f"{API}/documents/{doc_id}", headers=user_a["headers"])
    assert rd.json()["pipeline_status"]["epub"] is True


def test_audiobook_upload_flips_pipeline(user_a):
    r = requests.post(f"{API}/documents", json={"title": "TEST_AudioPipe", "content": "<p>hi</p>"},
                      headers=user_a["headers"])
    doc_id = r.json()["id"]
    files = {"file": ("intro.mp3", b"ID3" + b"\x00" * 500, "audio/mpeg")}
    ru = requests.post(f"{API}/documents/{doc_id}/audiobook/upload", files=files, headers=user_a["headers"])
    assert ru.status_code == 200, ru.text
    rd = requests.get(f"{API}/documents/{doc_id}", headers=user_a["headers"])
    assert rd.json()["pipeline_status"]["audiobook"] is True
