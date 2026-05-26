"""
Audio Studio backend tests — TTS preview + Audiobook download.
Iteration 5 — Divine Leadership Press.
Real OpenAI TTS calls via Emergent universal key. Kept minimal:
- 1 successful preview
- 1 successful audiobook (short doc, single chunk)
- All error/edge cases
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://editorial-studio-19.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

EXPECTED_VOICES = {"alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}


# ---- Fixtures ----

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_user(session):
    """Register a fresh test user and return (token, user_id)."""
    email = f"TEST_audio_{uuid.uuid4().hex[:8]}_{int(time.time())}@example.com"
    payload = {"email": email, "name": "Audio Tester", "password": "Pass1234!"}
    r = session.post(f"{API}/auth/register", json=payload, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return data["token"], data["user"]["id"], email


@pytest.fixture(scope="module")
def auth_headers(auth_user):
    token, _, _ = auth_user
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def short_doc(session, auth_headers):
    """Create a SHORT document (single TTS chunk)."""
    payload = {
        "title": "TEST_Audio_Short",
        "content": "<p>Welcome to Divine Leadership Press. This is a short manuscript.</p>",
        "format": "6x9",
    }
    r = session.post(f"{API}/documents", json=payload, headers=auth_headers, timeout=30)
    assert r.status_code == 200, f"create doc failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def empty_doc(session, auth_headers):
    payload = {"title": "TEST_Audio_Empty", "content": "", "format": "6x9"}
    r = session.post(f"{API}/documents", json=payload, headers=auth_headers, timeout=30)
    assert r.status_code == 200
    return r.json()


# ---- /api/tts/voices (public) ----

class TestVoicesCatalog:
    def test_voices_public_no_auth_required(self, session):
        r = session.get(f"{API}/tts/voices", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "voices" in data
        assert isinstance(data["voices"], list)
        assert len(data["voices"]) == 9
        keys = {v["key"] for v in data["voices"]}
        assert keys == EXPECTED_VOICES
        # Each voice has a label
        for v in data["voices"]:
            assert "label" in v and isinstance(v["label"], str) and len(v["label"]) > 0


# ---- /api/tts/preview ----

def _is_mp3_frame(b: bytes) -> bool:
    """MP3 frame sync: first byte 0xFF, second byte high nibble 0xF (>= 0xE0).
    Also accept ID3 tag prefix (some encoders prepend ID3v2)."""
    if not b or len(b) < 4:
        return False
    if b[:3] == b"ID3":
        return True
    return b[0] == 0xFF and (b[1] & 0xE0) == 0xE0


class TestTtsPreview:
    def test_preview_unauthenticated_returns_401(self, session):
        r = session.post(
            f"{API}/tts/preview",
            json={"text": "Hello", "voice": "onyx", "speed": 1.0},
            timeout=15,
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_preview_missing_text_and_content_returns_400(self, session, auth_headers):
        r = session.post(f"{API}/tts/preview", json={"voice": "onyx"}, headers=auth_headers, timeout=15)
        assert r.status_code == 400
        assert "text" in r.json().get("detail", "").lower() or "content" in r.json().get("detail", "").lower()

    def test_preview_text_too_long_returns_400(self, session, auth_headers):
        long_text = "a " * 2500  # > 4096 chars
        r = session.post(
            f"{API}/tts/preview",
            json={"text": long_text, "voice": "onyx"},
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 400
        detail = r.json().get("detail", "").lower()
        assert "4096" in detail or "limit" in detail or "audiobook" in detail

    def test_preview_success_with_text(self, session, auth_headers):
        r = session.post(
            f"{API}/tts/preview",
            json={"text": "Welcome to Divine Leadership Press.", "voice": "onyx", "speed": 1.0},
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"unexpected: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("audio/mpeg")
        body = r.content
        assert len(body) > 1000, "MP3 body too small"
        assert _is_mp3_frame(body), f"not an MP3 frame: first bytes={body[:4].hex()}"

    def test_preview_success_with_html_content(self, session, auth_headers):
        r = session.post(
            f"{API}/tts/preview",
            json={"content": "<p>Some <b>HTML</b> content for narration.</p>", "voice": "fable"},
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"unexpected: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("audio/mpeg")
        assert _is_mp3_frame(r.content)


# ---- /api/documents/{id}/audiobook ----

class TestAudiobook:
    def test_audiobook_success_short_doc(self, session, auth_headers, short_doc):
        r = session.post(
            f"{API}/documents/{short_doc['id']}/audiobook",
            params={"voice": "onyx", "speed": 1.0},
            headers={"Authorization": auth_headers["Authorization"]},
            timeout=120,
        )
        assert r.status_code == 200, f"unexpected: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("audio/mpeg")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()
        assert cd.endswith('_audiobook.mp3"') or "_audiobook.mp3" in cd
        assert _is_mp3_frame(r.content)
        assert len(r.content) > 1000

    def test_audiobook_empty_doc_returns_413(self, session, auth_headers, empty_doc):
        r = session.post(
            f"{API}/documents/{empty_doc['id']}/audiobook",
            headers={"Authorization": auth_headers["Authorization"]},
            timeout=30,
        )
        # ValueError -> 413 per code path; 400 acceptable per spec
        assert r.status_code in (400, 413, 502), f"expected 400/413/502, got {r.status_code}"

    def test_audiobook_not_owned_returns_404(self, session, short_doc):
        """Different user cannot access another's doc."""
        email = f"TEST_other_{uuid.uuid4().hex[:8]}@example.com"
        reg = session.post(
            f"{API}/auth/register",
            json={"email": email, "name": "Other", "password": "Pass1234!"},
            timeout=30,
        )
        assert reg.status_code == 200
        other_token = reg.json()["token"]
        r = session.post(
            f"{API}/documents/{short_doc['id']}/audiobook",
            headers={"Authorization": f"Bearer {other_token}"},
            timeout=30,
        )
        assert r.status_code == 404

    def test_audiobook_invalid_voice_silently_falls_back(self, session, auth_headers, short_doc):
        """Invalid voice should NOT 400 — it falls back to onyx silently."""
        r = session.post(
            f"{API}/documents/{short_doc['id']}/audiobook",
            params={"voice": "not-a-real-voice", "speed": 1.0},
            headers={"Authorization": auth_headers["Authorization"]},
            timeout=120,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("audio/mpeg")

    def test_audiobook_excessive_speed_clamps(self, session, auth_headers, short_doc):
        """speed=5.0 should clamp to 2.0 — no 400."""
        r = session.post(
            f"{API}/documents/{short_doc['id']}/audiobook",
            params={"voice": "onyx", "speed": 5.0},
            headers={"Authorization": auth_headers["Authorization"]},
            timeout=120,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("audio/mpeg")
