"""
Iteration 19 — ChatGPT (OpenAI) integration + BYO-key routing tests.

Covers:
  • GET /api/auth/me/llm-providers (public)
  • UserResponse has has_openai_key / has_anthropic_key / preferred_llm_provider
  • PUT/DELETE /api/auth/me/openai-key (validation, toggle flag)
  • PUT/DELETE /api/auth/me/anthropic-key (validation, toggle flag)
  • PUT /api/auth/me/preferred-provider (validation)
  • Agent chat: BYO key bypasses quota
  • Agent chat: fallback to DLP key decrements quota
  • Preference honoured by resolver
  • Inline Cmd-K: same BYO-key routing + response fields
"""
import os
import time
import uuid
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

FAKE_OPENAI_KEY = "sk-" + "a" * 30
FAKE_ANTHROPIC_KEY = "sk-ant-" + "b" * 30


# ---------- helpers ----------
def _register():
    email = f"test_iter19_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "name": "Iter19 User", "password": "Password1!",
    }, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    tok = r.json()["token"]
    return email, tok, {"Authorization": f"Bearer {tok}"}


def _create_doc(headers):
    r = requests.post(f"{API}/documents", json={"title": "Iter19 Doc"}, headers=headers, timeout=15)
    assert r.status_code in (200, 201), f"doc create: {r.status_code} {r.text}"
    return r.json()["id"]


async def _mongo_set_openai_key(email, key):
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        await client[DB_NAME].users.update_one({"email": email}, {"$set": {"openai_api_key": key}})
    finally:
        client.close()


async def _mongo_set_anthropic_key(email, key):
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        await client[DB_NAME].users.update_one({"email": email}, {"$set": {"anthropic_api_key": key}})
    finally:
        client.close()


async def _mongo_get_agent_usage_count(email):
    """Sum of agent_usage counts for this user today (uuid)."""
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        u = await client[DB_NAME].users.find_one({"email": email}, {"id": 1})
        if not u:
            return 0
        total = 0
        async for row in client[DB_NAME].agent_usage.find({"user_id": u["id"]}):
            total += int(row.get("count", 0))
        return total
    finally:
        client.close()


# ---------- tests ----------

def test_public_llm_providers_endpoint():
    """GET /api/auth/me/llm-providers is public + returns anthropic + openai."""
    r = requests.get(f"{API}/auth/me/llm-providers", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["default"] == "anthropic"
    provs = {p["key"]: p for p in data["providers"]}
    assert "anthropic" in provs and "openai" in provs
    assert provs["anthropic"]["model"] == "claude-sonnet-4-5-20250929"
    assert provs["openai"]["model"] == "gpt-5.4"
    assert provs["anthropic"]["label"] == "Claude (Sonnet 4.5)"
    assert provs["openai"]["label"] == "ChatGPT (GPT-5.4)"


def test_me_returns_new_fields_defaults():
    _, _, headers = _register()
    r = requests.get(f"{API}/auth/me", headers=headers, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["has_openai_key"] is False
    assert d["has_anthropic_key"] is False
    assert d["preferred_llm_provider"] == "anthropic"


def test_set_and_clear_openai_key():
    _, _, headers = _register()
    # invalid: too short
    r = requests.put(f"{API}/auth/me/openai-key", json={"api_key": "sk-short"}, headers=headers, timeout=15)
    assert r.status_code == 400
    assert "sk-" in r.text and "20" in r.text
    # invalid: no sk- prefix
    r = requests.put(f"{API}/auth/me/openai-key", json={"api_key": "x" * 40}, headers=headers, timeout=15)
    assert r.status_code == 400

    # valid
    r = requests.put(f"{API}/auth/me/openai-key", json={"api_key": FAKE_OPENAI_KEY}, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["has_openai_key"] is True
    assert d["has_anthropic_key"] is False

    # DELETE
    r = requests.delete(f"{API}/auth/me/openai-key", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["has_openai_key"] is False


def test_set_and_clear_anthropic_key():
    _, _, headers = _register()
    r = requests.put(f"{API}/auth/me/anthropic-key", json={"api_key": "sk-tiny"}, headers=headers, timeout=15)
    assert r.status_code == 400

    r = requests.put(f"{API}/auth/me/anthropic-key", json={"api_key": FAKE_ANTHROPIC_KEY}, headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["has_anthropic_key"] is True

    r = requests.delete(f"{API}/auth/me/anthropic-key", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["has_anthropic_key"] is False


def test_preferred_provider_toggle():
    _, _, headers = _register()
    r = requests.put(f"{API}/auth/me/preferred-provider", json={"provider": "openai"}, headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["preferred_llm_provider"] == "openai"

    r = requests.put(f"{API}/auth/me/preferred-provider", json={"provider": "anthropic"}, headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["preferred_llm_provider"] == "anthropic"

    r = requests.put(f"{API}/auth/me/preferred-provider", json={"provider": "foo"}, headers=headers, timeout=15)
    assert r.status_code == 400


def test_agent_chat_byo_key_bypasses_quota():
    """With a fake OpenAI key, /agent/chat should NEVER decrement quota, and response.byo_key=true."""
    email, _, headers = _register()
    doc_id = _create_doc(headers)

    # Inject fake key directly into Mongo
    asyncio.get_event_loop().run_until_complete(_mongo_set_openai_key(email, FAKE_OPENAI_KEY))

    # Baseline quota
    r = requests.get(f"{API}/ai/agent/quota", headers=headers, timeout=15)
    assert r.status_code == 200
    baseline = r.json()

    # Fire 3 chat calls — real LLM call will 502 because key is fake, that's OK
    seen_provider = None
    seen_model = None
    seen_byo = None
    for _ in range(3):
        r = requests.post(f"{API}/ai/agent/chat", json={
            "document_id": doc_id, "message": "Hi"
        }, headers=headers, timeout=45)
        # 502 (LLM failed) or 200 (very unlikely) — both fine as long as no quota was charged
        if r.status_code == 502:
            # Refund path — no data on provider in error response
            pass
        else:
            assert r.status_code == 200, r.text
            body = r.json()
            seen_provider = body.get("provider")
            seen_model = body.get("model")
            seen_byo = body.get("byo_key")

    # Verify quota unchanged
    r = requests.get(f"{API}/ai/agent/quota", headers=headers, timeout=15)
    assert r.status_code == 200
    after = r.json()
    # For free tier (no subscription) remaining should still equal 5
    if "remaining" in baseline and baseline.get("remaining") is not None:
        assert after["remaining"] == baseline["remaining"], f"quota changed: {baseline} -> {after}"

    # Also verify agent_usage collection stays at 0 for this user
    total = asyncio.get_event_loop().run_until_complete(_mongo_get_agent_usage_count(email))
    assert total == 0, f"agent_usage was charged despite BYO key: {total}"

    # If any call happened to return 200, verify provider/byo
    if seen_provider is not None:
        assert seen_byo is True
        assert seen_provider == "openai"
        assert "gpt" in (seen_model or "").lower()


def test_agent_chat_fallback_to_dlp_key_decrements_quota():
    """Fresh user with no BYO keys — should hit Emergent key and decrement quota."""
    _, _, headers = _register()
    doc_id = _create_doc(headers)

    r = requests.get(f"{API}/ai/agent/quota", headers=headers, timeout=15)
    baseline = r.json()

    r = requests.post(f"{API}/ai/agent/chat", json={
        "document_id": doc_id, "message": "Say hello in one word."
    }, headers=headers, timeout=90)
    assert r.status_code == 200, f"agent chat with DLP key failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("byo_key") is False
    assert body.get("provider") == "anthropic"
    assert "claude" in (body.get("model") or "").lower()

    r = requests.get(f"{API}/ai/agent/quota", headers=headers, timeout=15)
    after = r.json()
    if "remaining" in baseline and baseline.get("remaining") is not None:
        assert after["remaining"] == baseline["remaining"] - 1, f"quota did not decrement: {baseline} -> {after}"


def test_resolver_preference_with_only_openai_key_and_pref_anthropic():
    """User has only openai_api_key; preferred=anthropic. Resolver must pick openai (the one they have a key for)."""
    email, _, headers = _register()
    doc_id = _create_doc(headers)

    # Set fake openai key, keep preference at default anthropic
    asyncio.get_event_loop().run_until_complete(_mongo_set_openai_key(email, FAKE_OPENAI_KEY))

    r = requests.post(f"{API}/ai/agent/chat", json={
        "document_id": doc_id, "message": "Hi"
    }, headers=headers, timeout=45)
    # 502 expected (fake key), but the endpoint doesn't leak provider on error.
    # Fall back to inline command endpoint which also returns provider on success.
    # Instead: use resolver directly via a unit-style check — call the function.
    from writing_agent import resolve_provider_and_key
    prov, model, key, is_byo = resolve_provider_and_key(
        preferred_provider="anthropic",
        user_openai_key=FAKE_OPENAI_KEY,
        user_anthropic_key=None,
    )
    assert prov == "openai" and is_byo is True and key == FAKE_OPENAI_KEY

    # With BOTH keys → preferred wins
    prov, model, key, is_byo = resolve_provider_and_key(
        preferred_provider="anthropic",
        user_openai_key=FAKE_OPENAI_KEY,
        user_anthropic_key=FAKE_ANTHROPIC_KEY,
    )
    assert prov == "anthropic" and is_byo is True and key == FAKE_ANTHROPIC_KEY

    # No keys → preferred on Emergent key, is_byo=False
    prov, model, key, is_byo = resolve_provider_and_key(
        preferred_provider="openai",
        user_openai_key=None,
        user_anthropic_key=None,
    )
    assert prov == "openai" and is_byo is False


def test_inline_command_byo_routing():
    """/api/ai/agent/command should honour BYO key + include byo_key/provider/model in response."""
    _, _, headers = _register()
    doc_id = _create_doc(headers)

    # No BYO key → should succeed with DLP Emergent key, provider=anthropic
    r = requests.post(f"{API}/ai/agent/command", json={
        "document_id": doc_id,
        "selected_text": "The wind picked up.",
        "instruction": "Make it more vivid in one sentence.",
    }, headers=headers, timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("byo_key") is False
    assert body.get("provider") == "anthropic"
    assert "claude" in (body.get("model") or "").lower()
    assert "result" in body or "rewrite" in body or "text" in body or "reply" in body
