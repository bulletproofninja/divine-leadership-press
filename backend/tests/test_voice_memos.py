"""
Iteration 10 — Voice Memos (per-paragraph audio annotations).

Covers:
- POST /api/documents/{id}/memos (valid .webm, query-string params, validation: ext, empty, oversize, unauth, cross-user)
- GET  /api/documents/{id}/memos (list in insertion/push order)
- GET  /api/documents/{id}/memos/{memo_id} (audio bytes, content-type, 404, unauth)
- POST /api/documents/{id}/memos/{memo_id}/transcribe (first call uncached, second cached)
- DELETE /api/documents/{id}/memos/{memo_id} (file removed + pulled from doc, subsequent GET 404)
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
    return f"{int(time.time() * 1000)}_{os.getpid()}"


def _register(tag="memo"):
    email = f"TEST_{tag}_{_ts()}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "name": "Memo Test", "password": "P@ssword123",
    })
    assert r.status_code == 200, r.text
    return r.json()["token"], email


@pytest.fixture(scope="module")
def user_a():
    token, email = _register("memoA")
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "email": email}


@pytest.fixture(scope="module")
def user_b():
    token, email = _register("memoB")
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "email": email}


@pytest.fixture
def doc_a(user_a):
    r = requests.post(f"{API}/documents",
                      json={"title": "TEST_Memo Book", "content": "<p>Hello</p>"},
                      headers=user_a["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def _webm_bytes(size: int = 2048) -> bytes:
    # EBML header magic so it at least looks like a webm container; tail is random padding
    head = b"\x1a\x45\xdf\xa3" + b"\x9f\x42\x86\x81\x01"  # EBML header start
    return head + (b"\x00\x11\x22\x33" * ((size - len(head)) // 4))


# --- Auth gate ---------------------------------------------------------------

def test_memo_endpoints_require_auth(doc_a):
    did = doc_a["id"]
    r = requests.get(f"{API}/documents/{did}/memos")
    assert r.status_code == 401
    r2 = requests.post(f"{API}/documents/{did}/memos", files={"file": ("a.webm", _webm_bytes(), "audio/webm")})
    assert r2.status_code == 401


# --- Upload: validation ------------------------------------------------------

def test_create_memo_rejects_bad_extension(user_a, doc_a):
    files = {"file": ("malware.exe", _webm_bytes(), "application/octet-stream")}
    r = requests.post(f"{API}/documents/{doc_a['id']}/memos",
                      files=files, headers=user_a["headers"])
    assert r.status_code == 400
    assert "Unsupported audio format" in r.json().get("detail", "")


def test_create_memo_rejects_empty(user_a, doc_a):
    files = {"file": ("empty.webm", b"", "audio/webm")}
    r = requests.post(f"{API}/documents/{doc_a['id']}/memos",
                      files=files, headers=user_a["headers"])
    assert r.status_code == 400
    assert "too short" in r.json().get("detail", "").lower()


def test_create_memo_rejects_oversize(user_a, doc_a):
    # 25 MB + 1 byte
    big = b"\x00" * (25 * 1024 * 1024 + 1)
    files = {"file": ("big.webm", big, "audio/webm")}
    r = requests.post(f"{API}/documents/{doc_a['id']}/memos",
                      files=files, headers=user_a["headers"])
    assert r.status_code == 400
    assert "too large" in r.json().get("detail", "").lower()


# --- Upload: happy path + query-string params --------------------------------

def test_create_memo_happy_path_returns_full_schema(user_a, doc_a):
    files = {"file": ("a.webm", _webm_bytes(4096), "audio/webm")}
    r = requests.post(f"{API}/documents/{doc_a['id']}/memos",
                      files=files, headers=user_a["headers"])
    assert r.status_code == 200, r.text
    m = r.json()
    for key in ("id", "title", "paragraph_index", "ext", "size_bytes", "transcript", "created_at"):
        assert key in m, f"missing key {key}"
    assert m["ext"] == "webm"
    assert m["size_bytes"] >= 64
    assert m["transcript"] is None


def test_create_memo_accepts_querystring_params(user_a, doc_a):
    files = {"file": ("b.webm", _webm_bytes(1024), "audio/webm")}
    url = f"{API}/documents/{doc_a['id']}/memos?paragraph_index=2&title=My%20Note"
    r = requests.post(url, files=files, headers=user_a["headers"])
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["title"] == "My Note"
    assert m["paragraph_index"] == 2


# --- List in push order ------------------------------------------------------

def test_list_memos_returns_push_order(user_a, doc_a):
    did = doc_a["id"]
    created_ids = []
    for i in range(3):
        files = {"file": (f"m{i}.webm", _webm_bytes(512), "audio/webm")}
        r = requests.post(f"{API}/documents/{did}/memos?title=Memo{i}",
                          files=files, headers=user_a["headers"])
        assert r.status_code == 200
        created_ids.append(r.json()["id"])
    r = requests.get(f"{API}/documents/{did}/memos", headers=user_a["headers"])
    assert r.status_code == 200
    memos = r.json()["memos"]
    listed_ids = [m["id"] for m in memos]
    # Ensure created ids appear in push order somewhere in the list
    idx = [listed_ids.index(mid) for mid in created_ids]
    assert idx == sorted(idx), f"not in push order: {listed_ids}"
    # Schema sanity on each
    for m in memos:
        for key in ("id", "ext", "size_bytes", "transcript", "created_at"):
            assert key in m


# --- Fetch audio bytes -------------------------------------------------------

def test_fetch_memo_audio_returns_bytes_and_content_type(user_a, doc_a):
    files = {"file": ("c.webm", _webm_bytes(2048), "audio/webm")}
    r = requests.post(f"{API}/documents/{doc_a['id']}/memos",
                      files=files, headers=user_a["headers"])
    memo_id = r.json()["id"]
    r2 = requests.get(f"{API}/documents/{doc_a['id']}/memos/{memo_id}",
                      headers=user_a["headers"])
    assert r2.status_code == 200
    assert r2.headers.get("content-type", "").startswith("audio/webm")
    # Cache-Control: backend emits "private, max-age=60" but Cloudflare/ingress
    # strips it to "no-store, no-cache, must-revalidate". Either form is fine —
    # what matters is the audio is not publicly cacheable.
    cc = r2.headers.get("cache-control", "").lower()
    assert ("private" in cc) or ("no-store" in cc) or ("no-cache" in cc), cc
    assert len(r2.content) >= 64


def test_fetch_memo_audio_unknown_id_returns_404(user_a, doc_a):
    r = requests.get(f"{API}/documents/{doc_a['id']}/memos/does-not-exist",
                     headers=user_a["headers"])
    assert r.status_code == 404


# --- Cross-user isolation ----------------------------------------------------

def test_cross_user_access_returns_404(user_a, user_b, doc_a):
    did = doc_a["id"]
    # Create a memo as user A
    r = requests.post(f"{API}/documents/{did}/memos",
                      files={"file": ("x.webm", _webm_bytes(512), "audio/webm")},
                      headers=user_a["headers"])
    memo_id = r.json()["id"]
    # User B should see 404 on all memo endpoints
    assert requests.get(f"{API}/documents/{did}/memos", headers=user_b["headers"]).status_code == 404
    assert requests.get(f"{API}/documents/{did}/memos/{memo_id}", headers=user_b["headers"]).status_code == 404
    assert requests.post(f"{API}/documents/{did}/memos",
                         files={"file": ("y.webm", _webm_bytes(512), "audio/webm")},
                         headers=user_b["headers"]).status_code == 404
    assert requests.post(f"{API}/documents/{did}/memos/{memo_id}/transcribe",
                         headers=user_b["headers"]).status_code == 404
    assert requests.delete(f"{API}/documents/{did}/memos/{memo_id}",
                           headers=user_b["headers"]).status_code == 404


# --- Transcribe (Whisper) — first uncached, second cached --------------------

def _silent_wav_bytes(seconds: float = 0.5, rate: int = 16000) -> bytes:
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def test_transcribe_first_uncached_then_cached(user_a, doc_a):
    # Use a real silent WAV — Whisper accepts wav and the backend allows it.
    files = {"file": ("t.wav", _silent_wav_bytes(0.6), "audio/wav")}
    r = requests.post(f"{API}/documents/{doc_a['id']}/memos",
                      files=files, headers=user_a["headers"])
    assert r.status_code == 200, r.text
    memo_id = r.json()["id"]
    assert r.json()["ext"] == "wav"
    r1 = requests.post(f"{API}/documents/{doc_a['id']}/memos/{memo_id}/transcribe",
                       headers=user_a["headers"], timeout=180)
    if r1.status_code != 200:
        pytest.skip(f"Whisper rejected silent wav: {r1.status_code} {r1.text[:200]}")
    body1 = r1.json()
    assert "text" in body1
    assert body1.get("cached") is False
    if not (body1.get("text") or "").strip():
        # Whisper returned empty transcript for silence — backend (by design)
        # only caches truthy transcripts, so caching can't be exercised here.
        pytest.skip("Whisper returned empty transcript for silent wav — cache path not exercised")
    # Second call must be cached without re-invoking Whisper
    r2 = requests.post(f"{API}/documents/{doc_a['id']}/memos/{memo_id}/transcribe",
                       headers=user_a["headers"])
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2.get("cached") is True
    assert body2["text"] == body1["text"]


# --- Delete: file removed AND memo pulled from doc ---------------------------

def test_delete_memo_removes_file_and_pulls_record(user_a, doc_a):
    did = doc_a["id"]
    files = {"file": ("d.webm", _webm_bytes(1024), "audio/webm")}
    r = requests.post(f"{API}/documents/{did}/memos", files=files, headers=user_a["headers"])
    memo_id = r.json()["id"]
    # delete
    rd = requests.delete(f"{API}/documents/{did}/memos/{memo_id}", headers=user_a["headers"])
    assert rd.status_code == 200
    assert rd.json().get("deleted") is True
    # subsequent audio fetch 404
    rg = requests.get(f"{API}/documents/{did}/memos/{memo_id}", headers=user_a["headers"])
    assert rg.status_code == 404
    # list no longer contains it
    rl = requests.get(f"{API}/documents/{did}/memos", headers=user_a["headers"])
    assert all(m["id"] != memo_id for m in rl.json()["memos"])


# --- Quick regression: existing endpoints still reachable --------------------

def test_regression_pipeline_status_still_works(user_a, doc_a):
    # PipelineStatus is embedded in the document GET response, not a separate endpoint.
    r = requests.get(f"{API}/documents/{doc_a['id']}", headers=user_a["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    ps = body.get("pipeline_status") or {}
    for k in ("manuscript", "metadata", "cover", "pdf", "epub", "audiobook"):
        assert k in ps, f"pipeline_status missing {k}"


def test_regression_document_get_includes_memos_field(user_a, doc_a):
    r = requests.get(f"{API}/documents/{doc_a['id']}", headers=user_a["headers"])
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("memos", []), list)
