"""
Full-fledged copy-editing engine for Divine Leadership Press.
Powered by Claude Sonnet 4.5 with structured JSON output, paired with
deterministic local readability metrics.
"""
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from emergentintegrations.llm.chat import LlmChat, UserMessage
from house_style import EDITORIAL_POLICY, follows_house_style


MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"

CATEGORIES = [
    "grammar", "punctuation", "spelling", "run_on", "comma_splice",
    "passive", "wordy", "repetition", "consistency", "clarity", "tone",
]
SEVERITIES = ["must_fix", "suggested", "stylistic"]

STYLE_GUIDES = {
    "chicago": "Chicago Manual baseline for books, with Oxford commas and no em dashes.",
    "ap": "AP baseline for journalism, with no Oxford comma, concise prose, and no em dashes.",
    "mla": "MLA baseline for academic work, with Oxford commas, italicized titles, and no em dashes.",
    "house": "Divine Leadership Press house style, with serial commas, restrained prose, author-protective editing, and no em dashes.",
}

SYSTEM_PROMPT = (
    "You are a senior copy editor at Divine Leadership Press, a century-old "
    "publishing house. You are exacting, conservative, and respect the author's "
    "voice. You return ONLY valid JSON in the exact schema requested, with no "
    "preamble or commentary.\n\n" + EDITORIAL_POLICY
)


# ---------------------------------------------------------------------------
# Plain-text helpers
# ---------------------------------------------------------------------------
def html_to_paragraphs(html: str) -> List[str]:
    """Convert HTML to a list of plain-text paragraphs (preserves order)."""
    soup = BeautifulSoup(html or "", "html.parser")
    paragraphs: List[str] = []
    for el in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]):
        text = el.get_text(separator=" ", strip=True)
        if text:
            paragraphs.append(text)
    if not paragraphs:
        # Fall back to raw text split
        raw = soup.get_text(separator="\n", strip=True)
        paragraphs = [p.strip() for p in raw.split("\n") if p.strip()]
    return paragraphs


# ---------------------------------------------------------------------------
# Local readability metrics (deterministic)
# ---------------------------------------------------------------------------
def _count_syllables(word: str) -> int:
    """Cheap heuristic syllable counter."""
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    # Count vowel groups
    groups = re.findall(r"[aeiouy]+", word)
    syl = max(1, len(groups))
    # Silent trailing 'e'
    if word.endswith("e") and syl > 1 and not word.endswith("le"):
        syl -= 1
    return syl


PASSIVE_RE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(\w+(?:ed|en))\b",
    re.IGNORECASE,
)
ADVERB_RE = re.compile(r"\b\w+ly\b", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")


def compute_readability(paragraphs: List[str]) -> Dict[str, Any]:
    full = " ".join(paragraphs).strip()
    if not full:
        return {
            "fk_grade": 0, "avg_sentence_length": 0, "passive_pct": 0,
            "adverb_pct": 0, "sentence_count": 0, "word_count": 0,
            "longest_sentence": "",
        }

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(full) if s.strip()]
    if not sentences:
        sentences = [full]
    words = re.findall(r"\b[\w']+\b", full)
    word_count = len(words)
    sent_count = len(sentences)
    syllables = sum(_count_syllables(w) for w in words)

    fk_grade = (
        0.39 * (word_count / sent_count) + 11.8 * (syllables / max(word_count, 1)) - 15.59
        if word_count and sent_count else 0
    )

    passive_hits = len(PASSIVE_RE.findall(full))
    adverb_hits = len(ADVERB_RE.findall(full))

    longest = max(sentences, key=lambda s: len(s.split()))

    return {
        "fk_grade": round(fk_grade, 1),
        "avg_sentence_length": round(word_count / max(sent_count, 1), 1),
        "passive_pct": round(100 * passive_hits / max(sent_count, 1), 1),
        "adverb_pct": round(100 * adverb_hits / max(word_count, 1), 1),
        "sentence_count": sent_count,
        "word_count": word_count,
        "longest_sentence": longest if len(longest) <= 400 else longest[:400] + "…",
        "longest_sentence_words": len(longest.split()),
    }


# ---------------------------------------------------------------------------
# Claude copy-edit pass
# ---------------------------------------------------------------------------
def _build_manuscript_block(paragraphs: List[str], max_chars: int = 14000) -> str:
    lines: List[str] = []
    total = 0
    for idx, para in enumerate(paragraphs):
        block = f"[P{idx}] {para}"
        if total + len(block) > max_chars:
            lines.append(f"[...{len(paragraphs) - idx} more paragraphs truncated for length...]")
            break
        lines.append(block)
        total += len(block) + 1
    return "\n\n".join(lines)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def run_copyedit_pass(
    *,
    html_content: str,
    style_guide: str = "house",
) -> Dict[str, Any]:
    """Return {issues, readability, style_guide, paragraph_count}."""
    paragraphs = html_to_paragraphs(html_content)
    readability = compute_readability(paragraphs)

    if not paragraphs:
        return {
            "issues": [], "readability": readability,
            "style_guide": style_guide, "paragraph_count": 0,
        }

    guide_text = STYLE_GUIDES.get(style_guide, STYLE_GUIDES["house"])
    manuscript = _build_manuscript_block(paragraphs)

    prompt = f"""Perform a full copy-edit pass on the manuscript below. Apply {guide_text}

Identify every issue in these categories: {", ".join(CATEGORIES)}.

For each issue return an entry in a JSON object with this EXACT schema and nothing else:

{{
  "issues": [
    {{
      "category": "<one of: {', '.join(CATEGORIES)}>",
      "severity": "<one of: must_fix | suggested | stylistic>",
      "paragraph_index": <integer matching the [P#] marker>,
      "original": "<the exact substring as it appears in that paragraph; copy verbatim, including punctuation>",
      "suggestion": "<the corrected substring>",
      "rationale": "<one short sentence explaining the fix>"
    }}
  ]
}}

Rules:
- "original" MUST be a verbatim substring of the indicated paragraph so the editor can find it.
- Do not invent issues. Skip the issue if you cannot point to an exact substring.
- "must_fix" = grammar, punctuation, spelling, comma_splice, run_on.
- "suggested" = wordy, passive, repetition, consistency.
- "stylistic" = clarity, tone.
- Keep "original" as short as possible (a few words is ideal; whole clause only if needed).
- Return at most 60 issues, prioritising the highest severity.
- Output JSON only. No markdown fences, no commentary.
- Suggestions must never contain an em dash.

Manuscript:
---
{manuscript}
---"""

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"copyedit-{uuid.uuid4()}",
        system_message=SYSTEM_PROMPT,
    ).with_model(MODEL_PROVIDER, MODEL_NAME)

    raw = await chat.send_message(UserMessage(text=prompt))
    raw = _strip_code_fences(raw or "")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract the first {...} block
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise ValueError(f"Copy editor returned non-JSON output: {raw[:200]}")
        parsed = json.loads(match.group(0))

    issues_raw = parsed.get("issues", []) if isinstance(parsed, dict) else []
    cleaned: List[Dict[str, Any]] = []

    for issue in issues_raw:
        if not isinstance(issue, dict):
            continue
        category = str(issue.get("category", "")).strip().lower()
        severity = str(issue.get("severity", "")).strip().lower()
        original = issue.get("original")
        suggestion = issue.get("suggestion")
        rationale = issue.get("rationale", "")
        try:
            paragraph_index = int(issue.get("paragraph_index", -1))
        except (TypeError, ValueError):
            paragraph_index = -1

        if (
            category not in CATEGORIES
            or severity not in SEVERITIES
            or not isinstance(original, str)
            or not isinstance(suggestion, str)
            or not follows_house_style(suggestion)
            or paragraph_index < 0
            or paragraph_index >= len(paragraphs)
        ):
            continue

        # Verify the substring actually appears in the indicated paragraph
        paragraph_text = paragraphs[paragraph_index]
        if original.strip() and original.strip() not in paragraph_text:
            # Try a loose whitespace-normalised match
            norm_para = re.sub(r"\s+", " ", paragraph_text)
            norm_orig = re.sub(r"\s+", " ", original.strip())
            if norm_orig not in norm_para:
                continue

        cleaned.append({
            "id": str(uuid.uuid4()),
            "category": category,
            "severity": severity,
            "paragraph_index": paragraph_index,
            "original": original,
            "suggestion": suggestion,
            "rationale": rationale or "",
        })

    # Sort: must_fix first, then suggested, then stylistic; within each by paragraph order
    sev_order = {"must_fix": 0, "suggested": 1, "stylistic": 2}
    cleaned.sort(key=lambda i: (sev_order.get(i["severity"], 9), i["paragraph_index"]))

    return {
        "issues": cleaned,
        "readability": readability,
        "style_guide": style_guide,
        "paragraph_count": len(paragraphs),
    }
