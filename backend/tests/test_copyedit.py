"""Backend tests for Divine Leadership Press copy-edit endpoints.

Coverage:
- GET /api/copyedit/style-guides  -- public, 4 keys
- POST /api/documents/{id}/copyedit -- single real Claude call (full pass)
- Error paths: empty doc 400, unauthenticated 401, cross-user 404
- Invalid style_guide defaults to chicago silently
- Issue schema + 'original' substring + must_fix -> suggested -> stylistic sort
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

# Deliberately bad prose hitting comma_splice, spelling, repetition, passive
BAD_HTML = (
    "<h1>The Roof</h1>"
    "<p>It was raining, the streets were wet. The team have been working very very hard for many many days.</p>"
    "<p>She was given a book by John, the book was definately interesting. The proposal was reviewed by the committee.</p>"
    "<p>It is important to note that, in light of the fact that we are very very tired, we should rest.</p>"
)

VALID_CATEGORIES = {
    "grammar", "punctuation", "spelling", "run_on", "comma_splice",
    "passive", "wordy", "repetition", "consistency", "clarity", "tone",
}
VALID_SEVERITIES = {"must_fix", "suggested", "stylistic"}


@pytest.fixture(scope="module")
def session():
    return requests.Session()


def _register(session, suffix=""):
    ts = int(time.time() * 1000)
    email = f"TEST_ce_{suffix}_{ts}@example.com"
    r = session.post(f"{API}/auth/register", json={
        "email": email, "name": f"CE Tester {suffix}", "password": "Passw0rd!"
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
def doc_bad(session, user_a):
    r = session.post(f"{API}/documents", json={
        "title": "TEST_CE_Bad", "content": BAD_HTML
    }, headers=auth(user_a["token"]))
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
def doc_empty(session, user_a):
    r = session.post(f"{API}/documents", json={
        "title": "TEST_CE_Empty", "content": ""
    }, headers=auth(user_a["token"]))
    assert r.status_code == 200
    return r.json()["id"]


# Single real Claude call shared across multiple assertions ---------------
@pytest.fixture(scope="module")
def copyedit_result(session, user_a, doc_bad):
    r = session.post(
        f"{API}/documents/{doc_bad}/copyedit",
        json={"style_guide": "chicago"},
        headers=auth(user_a["token"]),
        timeout=120,
    )
    assert r.status_code == 200, r.text
    return r.json(), r.json().get("issues", [])


# --- Style guide catalog (public) ---
class TestStyleGuides:
    def test_list_no_auth_returns_4_guides(self, session):
        r = session.get(f"{API}/copyedit/style-guides")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "style_guides" in data
        keys = {g["key"] for g in data["style_guides"]}
        assert keys == {"chicago", "ap", "mla", "house"}, f"Got {keys}"
        # Every entry must carry a non-empty description
        for g in data["style_guides"]:
            assert isinstance(g.get("description"), str) and g["description"].strip()


# --- Happy path: ONE real Claude call ---
class TestCopyEditHappyPath:
    def test_response_shape(self, copyedit_result):
        result, _issues = copyedit_result
        for key in ("issues", "readability", "style_guide", "paragraph_count"):
            assert key in result, f"Missing top-level key: {key}"
        assert result["style_guide"] == "chicago"
        assert isinstance(result["issues"], list)
        assert isinstance(result["paragraph_count"], int) and result["paragraph_count"] > 0

    def test_readability_metrics(self, copyedit_result):
        result, _ = copyedit_result
        r = result["readability"]
        for k in ("fk_grade", "avg_sentence_length", "passive_pct",
                  "adverb_pct", "sentence_count", "word_count", "longest_sentence"):
            assert k in r, f"Missing readability key: {k}"
        # Numeric where applicable
        for num_k in ("fk_grade", "avg_sentence_length", "passive_pct",
                      "adverb_pct", "sentence_count", "word_count"):
            assert isinstance(r[num_k], (int, float)), f"{num_k} not numeric: {r[num_k]}"
        assert isinstance(r["longest_sentence"], str)
        assert r["word_count"] > 10
        assert r["sentence_count"] >= 3

    def test_issues_nonempty_and_schema(self, copyedit_result):
        result, issues = copyedit_result
        assert len(issues) >= 3, f"Expected several issues on bad prose, got {len(issues)}"
        for issue in issues:
            assert isinstance(issue["id"], str) and issue["id"]
            assert issue["category"] in VALID_CATEGORIES
            assert issue["severity"] in VALID_SEVERITIES
            assert isinstance(issue["paragraph_index"], int)
            assert issue["paragraph_index"] >= 0
            assert isinstance(issue["original"], str) and issue["original"]
            assert isinstance(issue["suggestion"], str)
            assert isinstance(issue["rationale"], str)

    def test_categories_cover_target_problems(self, copyedit_result):
        _, issues = copyedit_result
        cats = {i["category"] for i in issues}
        # Bad prose has explicit comma splice, misspelling 'definately',
        # passive voice, and 'very very' repetition. Expect at least one
        # from {comma_splice, spelling, passive, repetition, wordy}.
        target = {"comma_splice", "spelling", "passive", "repetition", "wordy"}
        assert cats & target, f"None of {target} surfaced; got {cats}"

    def test_issues_sorted_by_severity(self, copyedit_result):
        _, issues = copyedit_result
        order = {"must_fix": 0, "suggested": 1, "stylistic": 2}
        ranks = [order[i["severity"]] for i in issues]
        assert ranks == sorted(ranks), f"Issues not severity-sorted: {ranks}"

    def test_original_substring_present_in_paragraph(self, session, user_a, doc_bad, copyedit_result):
        # Pull the document's paragraphs via the readability helper indirectly:
        # We fetch the doc and confirm each issue's `original` (or its
        # whitespace-normalised form) appears in the indicated paragraph.
        import re
        from bs4 import BeautifulSoup
        r = session.get(f"{API}/documents/{doc_bad}", headers=auth(user_a["token"]))
        assert r.status_code == 200, r.text
        html = r.json().get("content") or ""
        soup = BeautifulSoup(html, "html.parser")
        paras = []
        for el in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]):
            t = el.get_text(separator=" ", strip=True)
            if t:
                paras.append(t)
        _, issues = copyedit_result
        for issue in issues:
            idx = issue["paragraph_index"]
            assert 0 <= idx < len(paras), f"Bad paragraph_index {idx} (only {len(paras)} paras)"
            para = paras[idx]
            orig = issue["original"]
            if orig.strip() in para:
                continue
            norm_para = re.sub(r"\s+", " ", para)
            norm_orig = re.sub(r"\s+", " ", orig.strip())
            assert norm_orig in norm_para, (
                f"Issue 'original' not found in paragraph {idx}: {orig!r}"
            )


# --- Invalid style guide defaults silently to chicago ---
class TestInvalidStyleGuide:
    def test_invalid_guide_defaults_chicago(self, session, user_a, doc_bad):
        r = session.post(
            f"{API}/documents/{doc_bad}/copyedit",
            json={"style_guide": "klingon"},
            headers=auth(user_a["token"]),
            timeout=120,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("style_guide") == "chicago"


# --- Error paths ---
class TestCopyEditErrors:
    def test_empty_document_returns_400(self, session, user_a, doc_empty):
        r = session.post(
            f"{API}/documents/{doc_empty}/copyedit",
            json={"style_guide": "chicago"},
            headers=auth(user_a["token"]),
        )
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_unauthenticated_returns_401(self, session, doc_bad):
        r = session.post(
            f"{API}/documents/{doc_bad}/copyedit",
            json={"style_guide": "chicago"},
        )
        assert r.status_code == 401

    def test_other_user_returns_404(self, session, user_b, doc_bad):
        r = session.post(
            f"{API}/documents/{doc_bad}/copyedit",
            json={"style_guide": "chicago"},
            headers=auth(user_b["token"]),
        )
        assert r.status_code == 404
