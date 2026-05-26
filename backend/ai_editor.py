"""
AI-assisted editorial tools for Divine Leadership Press.
Powered by Claude Sonnet 4.5 via the Emergent universal LLM key.
"""
import os
import re
import uuid
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"

SYSTEM_PROMPT = (
    "You are a senior literary editor at Divine Leadership Press, a century-old "
    "publishing house specialising in leadership and non-fiction. You write with "
    "restraint, precision, and respect for the author's voice. You return ONLY the "
    "requested output — no preamble, no commentary, no 'Here is...' phrases."
)


def _strip_html(html: str) -> str:
    """Convert simple HTML to plain text for prompts."""
    text = re.sub(r"<br\s*/?>", "\n", html or "")
    text = re.sub(r"</p\s*>", "\n\n", text)
    text = re.sub(r"</(h[1-6])\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate_for_context(text: str, max_chars: int = 12000) -> str:
    """Keep prompts within reasonable token budgets."""
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n\n[...content truncated for length...]\n\n{tail}"


async def _ask_claude(prompt: str) -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"editorial-{uuid.uuid4()}",
        system_message=SYSTEM_PROMPT,
    ).with_model(MODEL_PROVIDER, MODEL_NAME)

    response = await chat.send_message(UserMessage(text=prompt))
    return (response or "").strip()


# ---------------------------------------------------------------------------
# Editorial tools
# ---------------------------------------------------------------------------
async def tighten_prose(html_content: str) -> str:
    text = _truncate_for_context(_strip_html(html_content))
    if not text:
        return ""
    prompt = (
        "Rewrite the following passage to be tighter and more direct while fully "
        "preserving the author's voice, meaning, tone, and any technical terms. "
        "Keep paragraph breaks. Aim for ~15–25% shorter. Return only the rewritten "
        "prose, with no commentary.\n\n"
        "---\n"
        f"{text}\n"
        "---"
    )
    return await _ask_claude(prompt)


async def improve_clarity(html_content: str) -> str:
    text = _truncate_for_context(_strip_html(html_content))
    if not text:
        return ""
    prompt = (
        "Rewrite the passage below to improve clarity and readability for a general "
        "adult reader (target Flesch–Kincaid grade level ~8). Preserve all factual "
        "claims, voice, and paragraph structure. Replace jargon with plain English "
        "where it does not lose meaning. Return only the rewritten prose.\n\n"
        "---\n"
        f"{text}\n"
        "---"
    )
    return await _ask_claude(prompt)


async def generate_blurb(html_content: str, title: Optional[str], author: Optional[str]) -> str:
    text = _truncate_for_context(_strip_html(html_content), max_chars=8000)
    if not text:
        return ""
    prompt = (
        f"Write a compelling back-cover blurb for the book titled "
        f"\"{title or 'Untitled'}\""
        + (f" by {author}" if author else "")
        + ". The blurb must be 130–160 words, marketable, written in third person "
        "(unless the book is clearly memoir), open with a hook, end with a line "
        "that invites the reader in, and feel literary rather than salesy. Return "
        "only the blurb — no headings, no quotation marks.\n\n"
        "Manuscript excerpt:\n---\n"
        f"{text}\n"
        "---"
    )
    return await _ask_claude(prompt)


async def suggest_chapter_titles(html_content: str) -> str:
    """Return a newline-separated list of chapter titles."""
    text = _truncate_for_context(_strip_html(html_content))
    if not text:
        return ""

    # Find existing H1 chapters; if present, ask Claude to title each
    matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html_content or "", flags=re.IGNORECASE | re.DOTALL)
    if matches:
        prompt = (
            "Below is a manuscript whose chapters are currently marked by H1 headings. "
            f"There are {len(matches)} chapters. Propose a fresh, evocative title for "
            "each chapter, in order. Titles should be short (2–6 words), avoid clichés, "
            "and match a serious literary/non-fiction register. Return one title per "
            "line, numbered (e.g. '1. Title'). No commentary.\n\n"
            "Current chapter headings (for reference):\n"
            + "\n".join(f"- {re.sub('<[^>]+>', '', m).strip() or '(untitled)'}" for m in matches)
            + "\n\nManuscript:\n---\n"
            + text
            + "\n---"
        )
    else:
        prompt = (
            "Read the manuscript below and propose 8 evocative chapter titles that "
            "could structure it into a book. Titles should be short (2–6 words), "
            "avoid clichés, and feel literary. Return one title per line, numbered "
            "(e.g. '1. Title'). No commentary.\n\n"
            "Manuscript:\n---\n"
            f"{text}\n"
            "---"
        )
    return await _ask_claude(prompt)


async def generate_synopsis(html_content: str, title: Optional[str], author: Optional[str]) -> str:
    text = _truncate_for_context(_strip_html(html_content), max_chars=10000)
    if not text:
        return ""
    prompt = (
        f"Write a one-page synopsis (350–500 words) of the manuscript titled "
        f"\"{title or 'Untitled'}\""
        + (f" by {author}" if author else "")
        + ". The synopsis should suit a query letter and an Amazon KDP listing: "
        "establish the premise in the first paragraph, summarise the core argument "
        "or narrative arc, and close with the book's significance for its intended "
        "reader. Plain prose, no bullet points, no headings. Return only the synopsis.\n\n"
        "Manuscript:\n---\n"
        f"{text}\n"
        "---"
    )
    return await _ask_claude(prompt)
