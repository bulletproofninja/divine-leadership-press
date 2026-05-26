"""
Whisper-powered dictation for Divine Leadership Press.
Transcribes user microphone recordings into manuscript text.
"""
import io
import os
import re
from typing import Optional

from emergentintegrations.llm.openai import OpenAISpeechToText


WHISPER_MODEL = "whisper-1"
MAX_BYTES = 24 * 1024 * 1024  # safe under OpenAI's 25 MB cap

DICTATION_PROMPT = (
    "This is dictation for a book manuscript. Use proper punctuation, "
    "paragraph breaks, capitalisation, and standard book style."
)


def _get_client() -> OpenAISpeechToText:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")
    return OpenAISpeechToText(api_key=api_key)


async def transcribe_audio(
    *,
    data: bytes,
    filename: str = "recording.webm",
    language: Optional[str] = None,
    prompt: Optional[str] = None,
) -> str:
    """Send raw audio bytes to Whisper and return the transcript text."""
    if not data:
        raise ValueError("No audio data received.")
    if len(data) > MAX_BYTES:
        raise ValueError(
            f"Audio is too large ({len(data) // (1024 * 1024)} MB). "
            "Whisper accepts up to 25 MB per call."
        )

    client = _get_client()
    buffer = io.BytesIO(data)
    buffer.name = filename or "recording.webm"

    kwargs = {"file": buffer, "model": WHISPER_MODEL, "response_format": "text"}
    if language:
        kwargs["language"] = language
    kwargs["prompt"] = prompt or DICTATION_PROMPT

    response = await client.transcribe(**kwargs)

    # When response_format="text", emergentintegrations returns a plain string;
    # when "json", it returns an object with `.text`.
    if isinstance(response, str):
        text = response
    else:
        text = getattr(response, "text", "") or ""
    return _clean(text)


def _clean(text: str) -> str:
    text = (text or "").strip()
    # Collapse 3+ blank lines, normalise whitespace inside paragraphs
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
