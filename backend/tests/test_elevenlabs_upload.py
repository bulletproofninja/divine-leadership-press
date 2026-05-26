"""
Iteration 6 — ElevenLabs integration + Audiobook MP3 uploads.

Covers:
- /api/auth/me — has_elevenlabs_key field
- PUT/DELETE /api/auth/me/elevenlabs-key — validation, persistence
- GET /api/elevenlabs/voices — no-key 400, fake-key 401 (real ElevenLabs rejection)
- POST /api/elevenlabs/preview — no-key, missing voice_id, fake-key auth path
- POST /api/documents/{id}/elevenlabs-audiobook — cross-user 404
- POST /api/documents/{id}/audiobook/upload — happy path, bad ext, empty, cross-user
- GET /api/documents/{id}/audiobook — fetch back
- GET /api/documents/{id}/audiobook/info — before/after upload
- DELETE /api/documents/{id}/audiobook — delete + verify
- Auth gates on all the above
"""
import os
import time
import pytest
import requests

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        # Fall back to reading frontend/.env directly
        env_path = "/app/frontend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    return url.rstrip("/")


BASE_URL = _load_backend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

# A long fake ElevenLabs key — ≥20 chars to pass server-side validation
FAKE_EL_KEY = "sk_fake_1234567890abcdefghijklmn"  # 32 chars


def _register(suffix=""):
    ts = int(time.time() * 1000)
    email = f"TEST_el_{ts}{suffix}@example.com"
    resp = requests.post(
        f"{API}/auth/register",
        json={"email": email, "name": "Tester", "password": "P@ssword123"},
        timeout=20,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def user_a():
    return _register("_a")


@pytest.fixture(scope="module")
def user_b():
    return _register("_b")


@pytest.fixture(scope="module")
def doc_a(user_a):
    r = requests.post(
        f"{API}/documents",
        headers=_auth(user_a["token"]),
        json={"title": "TEST_DOC_A", "content": "<p>Hello world from author A.</p>"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def doc_b(user_b):
    r = requests.post(
        f"{API}/documents",
        headers=_auth(user_b["token"]),
        json={"title": "TEST_DOC_B", "content": "<p>Author B doc.</p>"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ----- auth/me + key management -----

class TestKeyManagement:
    def test_me_initial_has_no_key(self, user_a):
        r = requests.get(f"{API}/auth/me", headers=_auth(user_a["token"]), timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == user_a["user"]["email"]
        assert body.get("has_elevenlabs_key") is False

    def test_put_key_too_short_rejected(self, user_a):
        r = requests.put(
            f"{API}/auth/me/elevenlabs-key",
            headers=_auth(user_a["token"]),
            json={"api_key": "short"},
            timeout=10,
        )
        assert r.status_code == 400
        assert "invalid" in r.json()["detail"].lower()

    def test_put_valid_key_sets_flag(self, user_a):
        r = requests.put(
            f"{API}/auth/me/elevenlabs-key",
            headers=_auth(user_a["token"]),
            json={"api_key": FAKE_EL_KEY},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json()["has_elevenlabs_key"] is True

        # GET /me reflects it
        me = requests.get(f"{API}/auth/me", headers=_auth(user_a["token"]), timeout=10).json()
        assert me["has_elevenlabs_key"] is True

    def test_delete_key_clears_flag(self, user_a):
        r = requests.delete(
            f"{API}/auth/me/elevenlabs-key",
            headers=_auth(user_a["token"]),
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["has_elevenlabs_key"] is False
        me = requests.get(f"{API}/auth/me", headers=_auth(user_a["token"]), timeout=10).json()
        assert me["has_elevenlabs_key"] is False
        # Re-save for later tests
        requests.put(
            f"{API}/auth/me/elevenlabs-key",
            headers=_auth(user_a["token"]),
            json={"api_key": FAKE_EL_KEY},
            timeout=10,
        )

    def test_key_endpoints_unauthenticated(self):
        assert requests.put(
            f"{API}/auth/me/elevenlabs-key", json={"api_key": FAKE_EL_KEY}, timeout=10
        ).status_code in (401, 403)
        assert requests.delete(f"{API}/auth/me/elevenlabs-key", timeout=10).status_code in (
            401,
            403,
        )


# ----- ElevenLabs voices / preview -----

class TestElevenLabsAPIs:
    def test_voices_no_key(self, user_b):
        # user_b has no key
        r = requests.get(
            f"{API}/elevenlabs/voices", headers=_auth(user_b["token"]), timeout=10
        )
        assert r.status_code == 400
        assert "no elevenlabs api key" in r.json()["detail"].lower()

    def test_voices_fake_key_returns_401(self, user_a):
        # user_a has FAKE_EL_KEY saved -> ElevenLabs side rejects
        r = requests.get(
            f"{API}/elevenlabs/voices", headers=_auth(user_a["token"]), timeout=30
        )
        assert r.status_code == 401, f"Expected 401 from ElevenLabs, got {r.status_code}: {r.text}"

    def test_preview_no_key(self, user_b):
        r = requests.post(
            f"{API}/elevenlabs/preview",
            headers=_auth(user_b["token"]),
            json={"text": "Hello", "voice_id": "abc123"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_preview_missing_voice_id(self, user_a):
        # Pydantic will reject missing required field with 422
        r = requests.post(
            f"{API}/elevenlabs/preview",
            headers=_auth(user_a["token"]),
            json={"text": "Hello"},
            timeout=15,
        )
        # voice_id is required by the model — FastAPI returns 422 for missing required field
        assert r.status_code in (400, 422), r.text

    def test_preview_empty_voice_id(self, user_a):
        r = requests.post(
            f"{API}/elevenlabs/preview",
            headers=_auth(user_a["token"]),
            json={"text": "Hello", "voice_id": ""},
            timeout=15,
        )
        assert r.status_code == 400
        assert "voice_id is required" in r.json()["detail"].lower()

    def test_preview_fake_key_returns_401(self, user_a):
        r = requests.post(
            f"{API}/elevenlabs/preview",
            headers=_auth(user_a["token"]),
            json={"text": "Hello world", "voice_id": "21m00Tcm4TlvDq8ikWAM"},
            timeout=30,
        )
        # Must not be 500 — should bubble auth failure
        assert r.status_code in (400, 401), f"Got {r.status_code}: {r.text}"
        assert r.status_code != 500

    def test_elevenlabs_audiobook_cross_user_404(self, user_a, doc_b):
        # user_a tries to call elevenlabs-audiobook on user_b's doc
        r = requests.post(
            f"{API}/documents/{doc_b['id']}/elevenlabs-audiobook",
            headers=_auth(user_a["token"]),
            params={"voice_id": "21m00Tcm4TlvDq8ikWAM"},
            timeout=15,
        )
        assert r.status_code == 404

    def test_elevenlabs_endpoints_unauthenticated(self):
        assert requests.get(f"{API}/elevenlabs/voices", timeout=10).status_code in (401, 403)
        assert (
            requests.post(
                f"{API}/elevenlabs/preview", json={"text": "x", "voice_id": "y"}, timeout=10
            ).status_code
            in (401, 403)
        )


# ----- Audiobook MP3 upload -----

MP3_MAGIC = b"ID3\x04\x00\x00" + b"\x00" * 60 + b"\xff\xfb\x90\x00" + b"\x00" * 256  # >64 bytes


class TestAudiobookUpload:
    def test_info_before_upload(self, user_a, doc_a):
        r = requests.get(
            f"{API}/documents/{doc_a['id']}/audiobook/info",
            headers=_auth(user_a["token"]),
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json() == {"uploaded": False}

    def test_upload_happy_path(self, user_a, doc_a):
        files = {"file": ("intro.mp3", MP3_MAGIC, "audio/mpeg")}
        r = requests.post(
            f"{API}/documents/{doc_a['id']}/audiobook/upload",
            headers=_auth(user_a["token"]),
            files=files,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["uploaded"] is True
        assert body["filename"].endswith(".mp3")
        assert body["size_bytes"] == len(MP3_MAGIC)

    def test_info_after_upload(self, user_a, doc_a):
        r = requests.get(
            f"{API}/documents/{doc_a['id']}/audiobook/info",
            headers=_auth(user_a["token"]),
            timeout=10,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["uploaded"] is True
        assert body["extension"] == "mp3"
        assert body["size_bytes"] == len(MP3_MAGIC)
        assert body["filename"].endswith(".mp3")

    def test_fetch_audiobook(self, user_a, doc_a):
        r = requests.get(
            f"{API}/documents/{doc_a['id']}/audiobook",
            headers=_auth(user_a["token"]),
            timeout=15,
        )
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("audio/mpeg")
        assert "filename=" in r.headers.get("content-disposition", "")
        assert r.content == MP3_MAGIC

    def test_upload_bad_extension(self, user_a, doc_a):
        files = {"file": ("malware.exe", MP3_MAGIC, "application/octet-stream")}
        r = requests.post(
            f"{API}/documents/{doc_a['id']}/audiobook/upload",
            headers=_auth(user_a["token"]),
            files=files,
            timeout=15,
        )
        assert r.status_code == 400
        assert "unsupported" in r.json()["detail"].lower()

    def test_upload_empty_bytes(self, user_a, doc_a):
        files = {"file": ("empty.mp3", b"", "audio/mpeg")}
        r = requests.post(
            f"{API}/documents/{doc_a['id']}/audiobook/upload",
            headers=_auth(user_a["token"]),
            files=files,
            timeout=15,
        )
        assert r.status_code == 400

    def test_upload_cross_user_404(self, user_a, doc_b):
        files = {"file": ("intro.mp3", MP3_MAGIC, "audio/mpeg")}
        r = requests.post(
            f"{API}/documents/{doc_b['id']}/audiobook/upload",
            headers=_auth(user_a["token"]),
            files=files,
            timeout=15,
        )
        assert r.status_code == 404

    def test_delete_audiobook(self, user_a, doc_a):
        r = requests.delete(
            f"{API}/documents/{doc_a['id']}/audiobook",
            headers=_auth(user_a["token"]),
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["deleted"] is True

        # Info after delete
        info = requests.get(
            f"{API}/documents/{doc_a['id']}/audiobook/info",
            headers=_auth(user_a["token"]),
            timeout=10,
        ).json()
        assert info == {"uploaded": False}

    def test_audiobook_endpoints_unauthenticated(self, doc_a):
        assert (
            requests.post(
                f"{API}/documents/{doc_a['id']}/audiobook/upload",
                files={"file": ("a.mp3", MP3_MAGIC, "audio/mpeg")},
                timeout=10,
            ).status_code
            in (401, 403)
        )
        assert (
            requests.get(f"{API}/documents/{doc_a['id']}/audiobook", timeout=10).status_code
            in (401, 403)
        )
        assert (
            requests.get(f"{API}/documents/{doc_a['id']}/audiobook/info", timeout=10).status_code
            in (401, 403)
        )
        assert (
            requests.delete(f"{API}/documents/{doc_a['id']}/audiobook", timeout=10).status_code
            in (401, 403)
        )
