"""
Iteration 8 — Dictation (Whisper STT) + Cover-image -> PDF + generic image -> PDF.

Tests:
- POST /api/transcribe (valid wav silence / invalid ext / empty / unauth / oversize)
- POST /api/documents/{id}/cover/pdf (no cover -> 404, with cover -> 200 PDF,
  trim=8.5x11 echoed, invalid trim defaults to 6x9, cross-user 404, unauth 401)
- POST /api/tools/image-to-pdf (valid JPG, non-image, no trim default, unauth)
"""
import io
import os
import struct
import time
import wave

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _ts():
    return str(int(time.time() * 1000))


def _register():
    email = f"TEST_dict_{_ts()}_{os.getpid()}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "name": "Dict Test", "password": "P@ssword123"
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
    r = requests.post(f"{API}/documents",
                      json={"title": "TEST_Dict Book", "content": ""},
                      headers=user_a["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def _silent_wav_bytes(seconds: float = 0.5, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        n = int(rate * seconds)
        wf.writeframes(struct.pack("<" + "h" * n, *([0] * n)))
    return buf.getvalue()


def _jpeg_bytes(size=(800, 1280), color=(11, 29, 58)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _upload_cover(headers, doc_id, ext="jpg"):
    files = {"file": (f"cover.{ext}", _jpeg_bytes(), f"image/{ext}")}
    return requests.post(f"{API}/documents/{doc_id}/cover/upload",
                         files=files, headers=headers)


# ---------- DICTATION ----------

def test_transcribe_unauthenticated():
    files = {"file": ("rec.wav", _silent_wav_bytes(), "audio/wav")}
    r = requests.post(f"{API}/transcribe", files=files)
    assert r.status_code in (401, 403), r.text


def test_transcribe_empty_file(user_a):
    files = {"file": ("rec.wav", b"", "audio/wav")}
    r = requests.post(f"{API}/transcribe", files=files, headers=user_a["headers"])
    assert r.status_code == 400, r.text
    assert "No audio data" in r.json().get("detail", "")


def test_transcribe_invalid_extension(user_a):
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    r = requests.post(f"{API}/transcribe", files=files, headers=user_a["headers"])
    # endpoint accepts file then Whisper rejects -> 502 OR 400 (validation)
    assert r.status_code in (400, 502), r.text


def test_transcribe_valid_silent_wav(user_a):
    files = {"file": ("rec.wav", _silent_wav_bytes(0.4), "audio/wav")}
    r = requests.post(f"{API}/transcribe", files=files, headers=user_a["headers"])
    # Whisper may succeed (returns empty) or fail (502) on minimal audio; both are acceptable
    if r.status_code == 200:
        body = r.json()
        assert "text" in body
        assert isinstance(body["text"], str)
    else:
        assert r.status_code == 502, r.text


def test_transcribe_oversize(user_a):
    # 25 MB bogus webm-named blob — should be rejected by size guard (>24 MB)
    big = b"\x00" * (24 * 1024 * 1024 + 1024)
    files = {"file": ("big.webm", big, "audio/webm")}
    r = requests.post(f"{API}/transcribe", files=files, headers=user_a["headers"])
    assert r.status_code == 400, r.text
    assert "too large" in r.json().get("detail", "").lower()


# ---------- COVER -> PDF ----------

def test_cover_pdf_no_cover_uploaded(user_a, fresh_doc):
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/pdf",
                      headers=user_a["headers"])
    assert r.status_code == 404, r.text
    assert "No cover" in r.json().get("detail", "")


def test_cover_pdf_with_cover_default_trim(user_a, fresh_doc):
    up = _upload_cover(user_a["headers"], fresh_doc["id"])
    assert up.status_code == 200, up.text
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/pdf",
                      headers=user_a["headers"])
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert "_cover_" in cd and ".pdf" in cd
    assert r.content[:4] == b"%PDF"


def test_cover_pdf_trim_8_5x11_echoed(user_a, fresh_doc):
    up = _upload_cover(user_a["headers"], fresh_doc["id"])
    assert up.status_code == 200, up.text
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/pdf?trim=8.5x11",
                     headers=user_a["headers"])
    assert r.status_code == 200, r.text
    assert r.headers.get("x-trim-size") == "8.5x11"
    cd = r.headers.get("content-disposition", "")
    assert "_cover_8.5x11.pdf" in cd
    assert r.content[:4] == b"%PDF"


def test_cover_pdf_invalid_trim_defaults_6x9(user_a, fresh_doc):
    up = _upload_cover(user_a["headers"], fresh_doc["id"])
    assert up.status_code == 200, up.text
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/pdf?trim=garbage",
                     headers=user_a["headers"])
    assert r.status_code == 200, r.text
    assert r.headers.get("x-trim-size") == "6x9"


def test_cover_pdf_cross_user_404(user_a, user_b, fresh_doc):
    _upload_cover(user_a["headers"], fresh_doc["id"])
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/pdf",
                     headers=user_b["headers"])
    assert r.status_code == 404, r.text


def test_cover_pdf_unauthenticated(fresh_doc):
    r = requests.post(f"{API}/documents/{fresh_doc['id']}/cover/pdf")
    assert r.status_code in (401, 403), r.text


# ---------- generic /tools/image-to-pdf ----------

def test_image_to_pdf_valid_jpg_6x9(user_a):
    files = {"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")}
    r = requests.post(f"{API}/tools/image-to-pdf?trim=6x9",
                     files=files, headers=user_a["headers"])
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    assert r.headers.get("x-trim-size") == "6x9"


def test_image_to_pdf_non_image_400(user_a):
    files = {"file": ("notes.txt", b"hello world", "text/plain")}
    r = requests.post(f"{API}/tools/image-to-pdf",
                     files=files, headers=user_a["headers"])
    assert r.status_code == 400, r.text
    assert "Could not read image" in r.json().get("detail", "")


def test_image_to_pdf_no_trim_defaults_6x9(user_a):
    files = {"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")}
    r = requests.post(f"{API}/tools/image-to-pdf",
                     files=files, headers=user_a["headers"])
    assert r.status_code == 200, r.text
    assert r.headers.get("x-trim-size") == "6x9"


def test_image_to_pdf_unauthenticated():
    files = {"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")}
    r = requests.post(f"{API}/tools/image-to-pdf", files=files)
    assert r.status_code in (401, 403), r.text


# ---------- regression: pipeline_status + cover endpoints still work ----------

def test_regression_pipeline_status_present(user_a, fresh_doc):
    r = requests.get(f"{API}/documents/{fresh_doc['id']}", headers=user_a["headers"])
    assert r.status_code == 200
    ps = r.json().get("pipeline_status")
    assert ps is not None
    for k in ("manuscript", "metadata", "cover", "pdf", "epub", "audiobook"):
        assert k in ps


def test_regression_cover_upload_and_get(user_a, fresh_doc):
    up = _upload_cover(user_a["headers"], fresh_doc["id"])
    assert up.status_code == 200, up.text
    g = requests.get(f"{API}/documents/{fresh_doc['id']}/cover", headers=user_a["headers"])
    assert g.status_code == 200
    assert g.headers.get("content-type", "").startswith("image/")
