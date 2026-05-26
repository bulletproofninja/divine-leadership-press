"""
ElevenLabs narrator — premium TTS + voice cloning for Divine Leadership Press.
Each author provides their own ElevenLabs API key (per-user).
"""
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs


# ElevenLabs accepts up to ~5000 chars per call (some endpoints up to 10K with TTS Pro);
# keep a safe cap.
CHUNK_LIMIT = 4800
PREVIEW_CHAR_LIMIT = 1500
MAX_AUDIOBOOK_CHARS = 100_000

DEFAULT_MODEL = "eleven_multilingual_v2"
TURBO_MODEL = "eleven_turbo_v2_5"


class ElevenLabsAuthError(Exception):
    pass


class ElevenLabsServiceError(Exception):
    pass


def _make_client(api_key: str) -> ElevenLabs:
    if not api_key or not api_key.strip():
        raise ElevenLabsAuthError("No ElevenLabs API key configured for this user.")
    return ElevenLabs(api_key=api_key)


def _strip_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    parts: List[str] = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]):
        text = el.get_text(separator=" ", strip=True)
        if text:
            if el.name.lower().startswith("h") and not text.endswith((".", "!", "?", ":")):
                text = text + "."
            parts.append(text)
    if not parts:
        return re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
    return "\n\n".join(parts)


def _chunk_text(text: str, max_chars: int = CHUNK_LIMIT) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    buf = ""
    for para in re.split(r"\n{2,}", text):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 2 <= max_chars:
            buf = f"{buf}\n\n{para}".strip() if buf else para
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(para) <= max_chars:
            buf = para
            continue
        for sent in re.split(r"(?<=[.!?])\s+", para):
            sent = sent.strip()
            if not sent:
                continue
            if len(buf) + len(sent) + 1 <= max_chars:
                buf = f"{buf} {sent}".strip()
            else:
                if buf:
                    chunks.append(buf)
                if len(sent) <= max_chars:
                    buf = sent
                else:
                    for i in range(0, len(sent), max_chars):
                        chunks.append(sent[i : i + max_chars])
                    buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def list_voices(api_key: str) -> List[Dict]:
    """Return all voices available to the user (stock library + cloned)."""
    client = _make_client(api_key)
    try:
        res = client.voices.get_all()
    except Exception as exc:  # noqa: BLE001
        raise ElevenLabsAuthError(f"Could not list voices: {exc}")

    out: List[Dict] = []
    for v in getattr(res, "voices", []) or []:
        labels = getattr(v, "labels", None) or {}
        out.append({
            "voice_id": v.voice_id,
            "name": v.name,
            "category": getattr(v, "category", None) or "generated",
            "description": (getattr(v, "description", None) or "").strip(),
            "labels": labels if isinstance(labels, dict) else {},
            "preview_url": getattr(v, "preview_url", None),
        })
    return out


def _synthesise(
    client: ElevenLabs,
    *,
    text: str,
    voice_id: str,
    model_id: str,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
) -> bytes:
    """One synchronous TTS call — returns raw MP3 bytes."""
    try:
        gen = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
                use_speaker_boost=True,
            ),
        )
        audio = b""
        for chunk in gen:
            if chunk:
                audio += chunk
        if not audio:
            raise ElevenLabsServiceError("ElevenLabs returned empty audio.")
        return audio
    except ElevenLabsServiceError:
        raise
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "unauthorized" in msg or "invalid api key" in msg or "401" in msg or "invalid_api_key" in msg:
            raise ElevenLabsAuthError("ElevenLabs API key was rejected. Check the key in your settings.")
        raise ElevenLabsServiceError(f"ElevenLabs TTS failed: {exc}")


def narrate_text(
    *,
    api_key: str,
    text: str,
    voice_id: str,
    model_id: str = DEFAULT_MODEL,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> bytes:
    text = (text or "").strip()
    if not text:
        raise ValueError("No text to narrate.")
    if len(text) > CHUNK_LIMIT:
        raise ValueError(
            f"Snippet is {len(text)} chars; per-call limit is {CHUNK_LIMIT}. "
            "Use the audiobook endpoint for longer text."
        )
    client = _make_client(api_key)
    return _synthesise(
        client, text=text, voice_id=voice_id, model_id=model_id,
        stability=stability, similarity_boost=similarity_boost,
    )


def narrate_preview(
    *,
    api_key: str,
    html_content: str,
    voice_id: str,
    model_id: str = DEFAULT_MODEL,
) -> bytes:
    plain = _strip_html(html_content)
    snippet = plain[:PREVIEW_CHAR_LIMIT]
    if len(plain) > PREVIEW_CHAR_LIMIT:
        m = list(re.finditer(r"[.!?]\s", snippet))
        if m:
            snippet = snippet[: m[-1].end()]
    return narrate_text(
        api_key=api_key, text=snippet, voice_id=voice_id, model_id=model_id,
    )


def narrate_audiobook(
    *,
    api_key: str,
    html_content: str,
    voice_id: str,
    model_id: str = DEFAULT_MODEL,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> bytes:
    plain = _strip_html(html_content)
    if not plain.strip():
        raise ValueError("Manuscript is empty.")
    if len(plain) > MAX_AUDIOBOOK_CHARS:
        raise ValueError(
            f"Manuscript is {len(plain):,} characters. Audiobook synthesis is limited to "
            f"{MAX_AUDIOBOOK_CHARS:,} characters per run (~17,000 words). "
            "Split your book into chapters."
        )
    client = _make_client(api_key)
    pieces: List[bytes] = []
    for chunk in _chunk_text(plain):
        pieces.append(_synthesise(
            client, text=chunk, voice_id=voice_id, model_id=model_id,
            stability=stability, similarity_boost=similarity_boost,
        ))
    return b"".join(pieces)
