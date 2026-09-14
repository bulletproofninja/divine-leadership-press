"""
Writing Agent — conversational AI co-author for Divine Leadership Press.

Two surfaces:
  1. **Chat** (`agent_chat`)        — persistent, per-document conversation. Claude
                                      has the current manuscript as context plus prior
                                      turns. Supports voice-matching by sampling
                                      existing chapters.
  2. **Inline Command** (`run_inline_command`) — Cmd-K behaviour. Given a selected
                                      passage + an instruction, returns the
                                      rewritten passage in plain text, so the
                                      frontend can show a diff and accept/reject.

Powered by Claude Sonnet 4.5 via the Emergent universal LLM key — same provider
as `ai_editor.py` / `ai_copyeditor.py`.
"""
from __future__ import annotations

import os
import re
import uuid
from typing import List, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage
from house_style import EDITORIAL_POLICY, remove_em_dashes

# Default provider + model per provider.
DEFAULT_PROVIDER = "anthropic"
PROVIDER_DEFAULT_MODEL = {
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai":    "gpt-5.4",
}
PROVIDER_LABELS = {
    "anthropic": "Claude (Sonnet 4.5)",
    "openai":    "ChatGPT (GPT-5.4)",
}


def resolve_provider_and_key(
    *,
    preferred_provider: Optional[str],
    user_openai_key: Optional[str],
    user_anthropic_key: Optional[str],
) -> tuple[str, str, str, bool]:
    """Pick the provider + api_key for a given user request.

    Precedence:
      1. Explicit user preference (`preferred_provider`) if that provider has a
         user-supplied key → BYO key, unlimited.
      2. Any provider the user has a BYO key for → BYO key, unlimited.
      3. Preferred provider (or default) on the DLP Emergent universal key
         → subject to quota.

    Returns (provider, model, api_key, is_byo).
    """
    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    keys = {"openai": (user_openai_key or "").strip(), "anthropic": (user_anthropic_key or "").strip()}
    pref = (preferred_provider or DEFAULT_PROVIDER).lower()
    if pref not in PROVIDER_DEFAULT_MODEL:
        pref = DEFAULT_PROVIDER

    # 1. Preferred provider with own key
    if keys.get(pref):
        return pref, PROVIDER_DEFAULT_MODEL[pref], keys[pref], True

    # 2. Any provider with own key
    for prov, key in keys.items():
        if key:
            return prov, PROVIDER_DEFAULT_MODEL[prov], key, True

    # 3. Fallback to Emergent key on preferred provider
    return pref, PROVIDER_DEFAULT_MODEL[pref], emergent_key, False

# Voice presets the writer can choose from.
VOICE_PRESETS: dict = {
    "match_my_voice": {
        "label": "Match my voice",
        "description": "Sample the writer's existing chapters and mirror their tone.",
    },
    "literary": {
        "label": "Literary",
        "description": "Considered, lyrical, image-driven. Think Marilynne Robinson, Anthony Doerr.",
    },
    "journalistic": {
        "label": "Journalistic",
        "description": "Clear, factual, lead-with-the-news. Think The Atlantic long-form.",
    },
    "conversational": {
        "label": "Conversational",
        "description": "Warm, direct, second-person where natural. Think Seth Godin.",
    },
    "formal_business": {
        "label": "Formal / business",
        "description": "Crisp, structured, executive-ready. Think HBR.",
    },
    "poetic": {
        "label": "Poetic",
        "description": "Compressed, rhythmic, sensory. Use sparingly.",
    },
    "scholarly": {
        "label": "Scholarly",
        "description": "Carefully argued, citation-aware, neutral register.",
    },
}

# Base system prompt — modified by voice and document context at runtime.
BASE_SYSTEM_PROMPT = (
    "You are the in-house writing partner at Divine Leadership Press, a "
    "century-old publishing house. You help authors draft, brainstorm, edit, "
    "and formalize their ideas in real time.\n\n"
    "Operating principles:\n"
    "  • Respect the author's voice; never override it without being asked.\n"
    "  • Default to brevity. If a question can be answered in a sentence, do "
    "    that; if asked to draft, draft the requested length.\n"
    "  • When the author asks you to rewrite or draft prose, return prose only "
    "    with no preamble, introductory phrases, or meta-commentary.\n"
    "  • When the author asks a question, answer plainly and end with a single, "
    "    sharp follow-up question if it would meaningfully advance the work.\n"
    "  • Never invent biographical facts about the author. If you need a name, "
    "    date, or quote you don't have, ask.\n"
    "  • If the manuscript is empty, help the author find their first sentence.\n\n"
    + EDITORIAL_POLICY
)


def _strip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html or "")
    text = re.sub(r"</p\s*>", "\n\n", text)
    text = re.sub(r"</(h[1-6])\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n\n[...content truncated for length...]\n\n{tail}"


def _voice_directive(voice: Optional[str], voice_sample: Optional[str]) -> str:
    if not voice or voice == "match_my_voice":
        if voice_sample:
            return (
                "VOICE: Match the author's voice. Below is a sample of their existing "
                "prose; mirror its sentence rhythm, vocabulary, and register without "
                "imitating specific phrasings.\n\n"
                f"VOICE SAMPLE:\n---\n{_truncate(voice_sample, 4000)}\n---\n"
            )
        return "VOICE: Neutral, literary register until you have a sample to mirror.\n"
    preset = VOICE_PRESETS.get(voice)
    if not preset:
        return "VOICE: Neutral, literary register.\n"
    return f"VOICE: {preset['label']}. {preset['description']}\n"


def _build_system_prompt(
    *,
    document_title: Optional[str],
    document_text: Optional[str],
    voice: Optional[str],
    voice_sample: Optional[str],
) -> str:
    parts = [BASE_SYSTEM_PROMPT, ""]
    parts.append(_voice_directive(voice, voice_sample))
    if document_title:
        parts.append(f"WORKING TITLE: {document_title}\n")
    if document_text:
        snippet = _truncate(document_text, 12000)
        parts.append(
            "CURRENT MANUSCRIPT (plain text; author may reference passages):\n"
            "---\n"
            f"{snippet}\n"
            "---\n"
        )
    else:
        parts.append("CURRENT MANUSCRIPT: (empty; the page is blank)\n")
    return "\n".join(parts)


async def agent_chat(
    *,
    user_message: str,
    history: List[dict],
    document_title: Optional[str],
    document_html: Optional[str],
    voice: Optional[str] = "match_my_voice",
    voice_sample: Optional[str] = None,
    session_id: Optional[str] = None,
    provider: str = DEFAULT_PROVIDER,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Send one turn to the writing agent, honouring prior conversation history.

    history: list of {role: 'user'|'assistant', content: str}, oldest first.
    Returns the assistant's reply (plain text).
    """
    resolved_key = (api_key or os.environ.get("EMERGENT_LLM_KEY", "")).strip()
    if not resolved_key:
        raise RuntimeError("No LLM API key configured (neither user-supplied nor EMERGENT_LLM_KEY).")
    resolved_provider = (provider or DEFAULT_PROVIDER).lower()
    if resolved_provider not in PROVIDER_DEFAULT_MODEL:
        resolved_provider = DEFAULT_PROVIDER
    resolved_model = model or PROVIDER_DEFAULT_MODEL[resolved_provider]

    document_text = _strip_html(document_html or "")
    system_prompt = _build_system_prompt(
        document_title=document_title,
        document_text=document_text,
        voice=voice,
        voice_sample=voice_sample,
    )

    chat = LlmChat(
        api_key=resolved_key,
        session_id=session_id or f"agent-{uuid.uuid4()}",
        system_message=system_prompt,
    ).with_model(resolved_provider, resolved_model)

    # Replay history as plain context inside the new user message, since the
    # emergentintegrations LlmChat ties session memory to its own session_id.
    # This guarantees identical context regardless of pod restarts.
    transcript_blocks: List[str] = []
    for turn in (history or [])[-20:]:  # cap history to last 20 turns
        role = (turn.get("role") or "").lower()
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            transcript_blocks.append(f"AUTHOR: {content}")
        elif role == "assistant":
            transcript_blocks.append(f"YOU: {content}")
    transcript = "\n\n".join(transcript_blocks)

    final_prompt = (
        (f"Earlier in this conversation:\n\n{transcript}\n\n---\n\n" if transcript else "")
        + f"AUTHOR (new message): {user_message}\n\nReply now."
    )

    response = await chat.send_message(UserMessage(text=final_prompt))
    return remove_em_dashes((response or "").strip())


# ---------------------------------------------------------------------------
# Inline Cmd-K command — selection + instruction → rewritten selection
# ---------------------------------------------------------------------------
INLINE_SYSTEM_PROMPT = (
    "You are the in-house writing partner at Divine Leadership Press. The "
    "author has highlighted a passage and given you a one-line instruction. "
    "Return ONLY the rewritten passage, with no preamble, commentary, or quote "
    "marks around it. Preserve any markdown / inline formatting present in the "
    "input. If the instruction asks for an EXPANSION, the result may be longer; "
    "otherwise keep similar length.\n\n" + EDITORIAL_POLICY
)


async def run_inline_command(
    *,
    selected_text: str,
    instruction: str,
    document_title: Optional[str] = None,
    voice: Optional[str] = "match_my_voice",
    voice_sample: Optional[str] = None,
    provider: str = DEFAULT_PROVIDER,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Execute a one-shot Cmd-K instruction against a highlighted passage."""
    resolved_key = (api_key or os.environ.get("EMERGENT_LLM_KEY", "")).strip()
    if not resolved_key:
        raise RuntimeError("No LLM API key configured (neither user-supplied nor EMERGENT_LLM_KEY).")
    resolved_provider = (provider or DEFAULT_PROVIDER).lower()
    if resolved_provider not in PROVIDER_DEFAULT_MODEL:
        resolved_provider = DEFAULT_PROVIDER
    resolved_model = model or PROVIDER_DEFAULT_MODEL[resolved_provider]

    selected_text = (selected_text or "").strip()
    instruction = (instruction or "").strip()
    if not selected_text:
        raise ValueError("No text selected.")
    if not instruction:
        raise ValueError("Instruction cannot be empty.")

    system_prompt = (
        INLINE_SYSTEM_PROMPT
        + "\n\n"
        + _voice_directive(voice, voice_sample)
        + (f"\nWORKING TITLE: {document_title}\n" if document_title else "")
    )

    chat = LlmChat(
        api_key=resolved_key,
        session_id=f"agent-inline-{uuid.uuid4()}",
        system_message=system_prompt,
    ).with_model(resolved_provider, resolved_model)

    prompt = (
        f"INSTRUCTION: {instruction}\n\n"
        f"PASSAGE:\n---\n{_truncate(selected_text, 6000)}\n---\n\n"
        "Rewrite the passage now. Return only the new passage."
    )
    response = await chat.send_message(UserMessage(text=prompt))
    return remove_em_dashes((response or "").strip())
