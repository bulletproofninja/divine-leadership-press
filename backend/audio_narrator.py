"""
Audio Studio — OpenAI TTS narration for Divine Leadership Press.
Powered by tts-1-hd via the Emergent universal LLM key.

Provides:
- Single-paragraph preview narration (≤4096 chars)
- Full-manuscript audiobook generation (chunked + concatenated MP3)
"""
import os
import re
from typing import List, Optional

from bs4 import BeautifulSoup
from emergentintegrations.llm.openai import OpenAITextToSpeech


VOICES = [
    {"key": "alloy", "label": "Alloy — Neutral, balanced"},
    {"key": "ash", "label": "Ash — Clear, articulate"},
    {"key": "coral", "label": "Coral — Warm, friendly"},
    {"key": "echo", "label": "Echo — Smooth, calm"},
    {"key": "fable", "label": "Fable — British, expressive, literary"},
    {"key": "nova", "label": "Nova — Energetic, upbeat"},
    {"key": "onyx", "label": "Onyx — Deep, authoritative"},
    {"key": "sage", "label": "Sage — Wise, measured"},
    {"key": "shimmer", "label": "Shimmer — Bright, cheerful"},
]
VOICE_KEYS = {v["key"] for v in VOICES}

# OpenAI TTS hard limit
TTS_CHAR_LIMIT = 4096

# Maximum manuscript size we'll narrate in a single request (~17K words).
# Larger manuscripts should be split into chapters; the endpoint returns 413.
MAX_AUDIOBOOK_CHARS = 100_000

# Soft cap for a "preview" narration so playback returns in a few seconds.
PREVIEW_CHAR_LIMIT = 1500


def list_voices() -> List[dict]:
    return list(VOICES)


def _strip_html(html: str) -> str:
    """Convert HTML to clean reading-friendly plain text."""
    soup = BeautifulSoup(html or "", "html.parser")
    parts: List[str] = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]):
        text = el.get_text(separator=" ", strip=True)
        if not text:
            continue
        # Add a brief pause after headings by ending with a period
        tag = el.name.lower()
        if tag.startswith("h") and not text.endswith((".", "!", "?", ":")):
            text = text + "."
        parts.append(text)
    if not parts:
        # Plain text fallback
        return re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
    return "\n\n".join(parts)


def _chunk_text(text: str, max_chars: int = TTS_CHAR_LIMIT) -> List[str]:
    """Split text into TTS-safe chunks at sentence boundaries when possible."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    # Walk paragraphs, then sentences, gluing together until we hit the cap.
    paragraphs = re.split(r"\n{2,}", text)
    buf = ""

    def _flush():
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
        buf = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 2 <= max_chars:
            buf = f"{buf}\n\n{para}".strip() if buf else para
            continue
        # Paragraph itself fits, but not in current buffer
        if len(para) <= max_chars:
            _flush()
            buf = para
            continue
        # Paragraph is itself larger than the limit — split by sentence
        sentences = re.split(r"(?<=[.!?])\s+", para)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(buf) + len(sent) + 1 <= max_chars:
                buf = f"{buf} {sent}".strip()
            else:
                _flush()
                if len(sent) <= max_chars:
                    buf = sent
                else:
                    # Sentence longer than limit — hard split
                    for i in range(0, len(sent), max_chars):
                        chunks.append(sent[i : i + max_chars])
                    buf = ""
    _flush()
    return chunks


def _get_tts_client() -> OpenAITextToSpeech:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")
    return OpenAITextToSpeech(api_key=api_key)


def _validate_voice(voice: Optional[str]) -> str:
    if voice and voice in VOICE_KEYS:
        return voice
    return "onyx"


def _validate_speed(speed: Optional[float]) -> float:
    try:
        s = float(speed) if speed is not None else 1.0
    except (TypeError, ValueError):
        s = 1.0
    return max(0.5, min(2.0, s))


async def narrate_text(
    *,
    text: str,
    voice: str = "onyx",
    speed: float = 1.0,
    model: str = "tts-1-hd",
) -> bytes:
    """Narrate a short snippet (≤4096 chars). Raises ValueError if too long."""
    text = (text or "").strip()
    if not text:
        raise ValueError("No text to narrate.")
    if len(text) > TTS_CHAR_LIMIT:
        raise ValueError(
            f"Snippet is {len(text)} chars; the TTS engine accepts at most {TTS_CHAR_LIMIT}. "
            "Use the Audiobook export for longer text."
        )
    tts = _get_tts_client()
    return await tts.generate_speech(
        text=text,
        model=model,
        voice=_validate_voice(voice),
        speed=_validate_speed(speed),
        response_format="mp3",
    )


async def narrate_preview(
    *,
    html_content: str,
    voice: str = "onyx",
    speed: float = 1.0,
) -> bytes:
    """Preview narration: first ~1500 plain-text characters of the manuscript."""
    plain = _strip_html(html_content)
    snippet = plain[:PREVIEW_CHAR_LIMIT]
    # Trim to nearest sentence boundary if possible
    if len(plain) > PREVIEW_CHAR_LIMIT:
        m = list(re.finditer(r"[.!?]\s", snippet))
        if m:
            snippet = snippet[: m[-1].end()]
    return await narrate_text(text=snippet, voice=voice, speed=speed)


async def narrate_audiobook(
    *,
    html_content: str,
    voice: str = "onyx",
    speed: float = 1.0,
    model: str = "tts-1-hd",
) -> bytes:
    """Generate a full MP3 audiobook by chunking + concatenation."""
    plain = _strip_html(html_content)
    if not plain.strip():
        raise ValueError("Manuscript is empty.")
    if len(plain) > MAX_AUDIOBOOK_CHARS:
        raise ValueError(
            f"Manuscript is {len(plain):,} characters. "
            f"Audiobook synthesis is currently limited to {MAX_AUDIOBOOK_CHARS:,} characters "
            "(~17,000 words). Split your book into chapters and generate one audiobook per chapter."
        )

    chunks = _chunk_text(plain)
    tts = _get_tts_client()

    pieces: List[bytes] = []
    for chunk in chunks:
        audio = await tts.generate_speech(
            text=chunk,
            model=model,
            voice=_validate_voice(voice),
            speed=_validate_speed(speed),
            response_format="mp3",
        )
        pieces.append(audio)

    # MP3 frames are concatenable: appending the bytes yields a single playable file.
    return b"".join(pieces)
