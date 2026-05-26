"""
Voice Memo storage — per-paragraph audio annotations attached to a manuscript.
Files live on disk under /app/backend/uploads/memos/{user_id}/{document_id}/{memo_id}.{ext}.
Metadata is embedded in the document.memos array.
"""
import os
import re
from pathlib import Path
from typing import Optional, Tuple

UPLOAD_ROOT = Path(os.environ.get("MEMO_UPLOAD_DIR", "/app/backend/uploads/memos"))

ALLOWED_EXTENSIONS = {"webm", "ogg", "mp3", "wav", "m4a"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB — keeps memos firmly under Whisper's cap


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", s or "")


def _safe_ext(filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return ext if ext in ALLOWED_EXTENSIONS else ""


def memo_dir(user_id: str, document_id: str) -> Path:
    p = UPLOAD_ROOT / _safe(user_id) / _safe(document_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def storage_path(user_id: str, document_id: str, memo_id: str, ext: str) -> Path:
    return memo_dir(user_id, document_id) / f"{_safe(memo_id)}.{ext}"


def find_memo_file(user_id: str, document_id: str, memo_id: str) -> Optional[Tuple[Path, str]]:
    d = UPLOAD_ROOT / _safe(user_id) / _safe(document_id)
    if not d.exists():
        return None
    for ext in ALLOWED_EXTENSIONS:
        p = d / f"{_safe(memo_id)}.{ext}"
        if p.exists():
            return p, ext
    return None


def save_memo(user_id: str, document_id: str, memo_id: str, filename: str, data: bytes) -> Tuple[Path, str]:
    ext = _safe_ext(filename)
    if not ext:
        raise ValueError(
            f"Unsupported audio format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Memo too large. Maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if len(data) < 64:
        raise ValueError("Recording too short.")
    path = storage_path(user_id, document_id, memo_id, ext)
    path.write_bytes(data)
    return path, ext


def delete_memo_file(user_id: str, document_id: str, memo_id: str) -> bool:
    found = find_memo_file(user_id, document_id, memo_id)
    if not found:
        return False
    try:
        found[0].unlink()
    except FileNotFoundError:
        return False
    return True


def media_type_for(ext: str) -> str:
    return {
        "webm": "audio/webm",
        "ogg": "audio/ogg",
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
    }.get(ext, "application/octet-stream")
