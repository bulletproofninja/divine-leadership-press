"""Backend tests for Divine Leadership Press AI editorial endpoints.

Coverage:
- GET /api/ai/tools (public)  -- returns 5 tool entries
- POST /api/documents/{id}/ai -- happy paths (tighten, blurb, chapter_titles)
- Error paths: invalid tool, empty content, unauthenticated, cross-user 404
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

SAMPLE_HTML = (
    "<h1>The Practice of Leadership</h1>"
    "<p>Leadership is not a title that one is granted upon promotion; rather, "
    "it is a practice that is cultivated, painstakingly and over many years, "
    "through the patient observation of human beings and the willingness to be "
    "wrong in public.</p>"
    "<p>The most effective leaders we have studied at length tend to share a "
    "single, quiet habit: they listen more than they speak, and when they do "
    "speak they ask better questions than they give answers.</p>"
    "<p>This book is an attempt to chart that habit — its origins, its costs, "
    "and the small daily exercises by which any reader may begin to acquire it.</p>"
)


@pytest.fixture(scope="module")
def session():
    return requests.Session()


def _register(session, suffix=""):
    ts = int(time.time() * 1000)
    email = f"TEST_ai_{suffix}_{ts}@example.com"
    r = session.post(f"{API}/auth/register", json={
        "email": email, "name": f"AI Tester {suffix}", "password": "Passw0rd!"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    return {"email": email, "token": data["token"], "id": data["user"]["id"]}


@pytest.fixture(scope="module")
def user_a(session):
    return _register(session, "a")


@pytest.fixture(scope="module")
def user_b(session):
    return _register(session, "b")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def doc_with_content(session, user_a):
    r = session.post(f"{API}/documents", json={
        "title": "TEST_AI_Doc",
        "content": SAMPLE_HTML,
    }, headers=auth(user_a["token"]))
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
def empty_doc(session, user_a):
    r = session.post(f"{API}/documents", json={
        "title": "TEST_AI_Empty",
        "content": "",
    }, headers=auth(user_a["token"]))
    assert r.status_code == 200
    return r.json()["id"]


# --- /api/ai/tools (public) ---
class TestAiToolsCatalog:
    def test_list_no_auth_returns_5_tools(self, session):
        r = session.get(f"{API}/ai/tools")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "tools" in data and isinstance(data["tools"], list)
        keys = {t["key"] for t in data["tools"]}
        expected = {"tighten", "clarity", "blurb", "chapter_titles", "synopsis"}
        assert keys == expected, f"Expected exactly 5 tools {expected}, got {keys}"
        # Each entry must carry a non-empty label
        for t in data["tools"]:
            assert t.get("label"), f"Empty label for {t}"


# --- Happy-path AI runs (real Claude calls - kept to a minimum) ---
class TestAiHappyPath:
    def test_tighten_returns_prose(self, session, user_a, doc_with_content):
        r = session.post(
            f"{API}/documents/{doc_with_content}/ai",
            json={"tool": "tighten"},
            headers=auth(user_a["token"]),
            timeout=90,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tool"] == "tighten"
        assert data["result_type"] == "prose"
        assert isinstance(data["result"], str)
        assert len(data["result"].strip()) > 50, "Tighten result too short"

    def test_blurb_returns_blurb_within_length(self, session, user_a, doc_with_content):
        r = session.post(
            f"{API}/documents/{doc_with_content}/ai",
            json={"tool": "blurb"},
            headers=auth(user_a["token"]),
            timeout=90,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tool"] == "blurb"
        assert data["result_type"] == "blurb"
        result = (data["result"] or "").strip()
        # Spec says 100-1000 chars
        assert 100 <= len(result) <= 1000, f"Blurb length {len(result)} outside 100-1000"

    def test_chapter_titles_returns_numbered_list(self, session, user_a, doc_with_content):
        r = session.post(
            f"{API}/documents/{doc_with_content}/ai",
            json={"tool": "chapter_titles"},
            headers=auth(user_a["token"]),
            timeout=90,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tool"] == "chapter_titles"
        assert data["result_type"] == "list"
        result = data["result"] or ""
        # Must contain at least one numbered line, e.g. "1. Title"
        import re
        assert re.search(r"(?m)^\s*\d+[\.\)]\s+\S", result), f"No numbered line in: {result[:200]}"


# --- Error paths ---
class TestAiErrors:
    def test_unknown_tool_returns_400(self, session, user_a, doc_with_content):
        r = session.post(
            f"{API}/documents/{doc_with_content}/ai",
            json={"tool": "bogus_tool"},
            headers=auth(user_a["token"]),
        )
        assert r.status_code == 400
        assert "unknown" in r.json()["detail"].lower()

    def test_empty_document_returns_400(self, session, user_a, empty_doc):
        r = session.post(
            f"{API}/documents/{empty_doc}/ai",
            json={"tool": "tighten"},
            headers=auth(user_a["token"]),
        )
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_unauthenticated_returns_401(self, session, doc_with_content):
        r = session.post(
            f"{API}/documents/{doc_with_content}/ai",
            json={"tool": "tighten"},
        )
        assert r.status_code == 401

    def test_other_user_returns_404(self, session, user_b, doc_with_content):
        r = session.post(
            f"{API}/documents/{doc_with_content}/ai",
            json={"tool": "tighten"},
            headers=auth(user_b["token"]),
        )
        assert r.status_code == 404
