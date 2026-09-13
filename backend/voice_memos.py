"""
Voice Memo storage — per-paragraph audio annotations attached to a manuscript.

Bytes are stored in Emergent Object Storage. Per-memo metadata lives inside
the `documents.memos[]` array; each memo carries its own `storage_path`.
"""
import re
from typing import Optional

from object_storage import APP_NAME, get_object, put_object

ALLOWED_EXTENSIONS = {"webm", "ogg", "mp3", "wav", "m4a"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB — Whisper cap headroom


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", s or "")


def _safe_ext(filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return ext if ext in ALLOWED_EXTENSIONS else ""


def media_type_for(ext: str) -> str:
    return {
        "webm": "audio/webm",
        "ogg": "audio/ogg",
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
    }.get(ext, "application/octet-stream")


def save_memo(
    user_id: str,
    document_id: str,
    memo_id: str,
    filename: str,
    data: bytes,
) -> dict:
    ext = _safe_ext(filename)
    if not ext:
        raise ValueError(
            f"Unsupported audio format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Memo too large. Maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    if len(data) < 64:
        raise ValueError("Recording too short.")
    path = (
        f"{APP_NAME}/memos/{_safe(user_id)}/{_safe(document_id)}/{_safe(memo_id)}.{ext}"
    )
    result = put_object(path, data, media_type_for(ext))
    return {
        "storage_path": result["path"],
        "ext": ext,
        "size": int(result.get("size") or len(data)),
    }


def find_memo_file(doc: dict, memo_id: str) -> Optional[dict]:
    for memo in (doc or {}).get("memos") or []:
        if memo.get("id") == memo_id and memo.get("storage_path"):
            return memo
    return None


def fetch_bytes(storage_path: str) -> bytes:
    data, _ = get_object(storage_path)
    return data


def delete_memo_file(doc: dict, memo_id: str) -> bool:
    """Soft-delete: caller pulls the memo from the array; storage has no DELETE."""
    return find_memo_file(doc, memo_id) is not None
