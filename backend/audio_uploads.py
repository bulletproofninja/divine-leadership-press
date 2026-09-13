"""
Audio uploads — store author-supplied audiobook files in Emergent Object Storage.

Metadata is kept on the parent `documents` record under `audio_upload`:
    {"storage_path": str, "ext": str, "size": int, "filename": str}
"""
import re
from typing import Optional

from object_storage import APP_NAME, get_object, put_object

ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "ogg", "flac"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", s or "")


def _safe_ext(filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return ext if ext in ALLOWED_EXTENSIONS else ""


def media_type_for(ext: str) -> str:
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
    }.get(ext, "application/octet-stream")


def save_upload(user_id: str, document_id: str, filename: str, data: bytes) -> dict:
    ext = _safe_ext(filename)
    if not ext:
        raise ValueError(
            f"Unsupported audio format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File too large. Maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    if len(data) < 64:
        raise ValueError("File appears to be empty.")
    path = f"{APP_NAME}/audio/{_safe(user_id)}/{_safe(document_id)}.{ext}"
    result = put_object(path, data, media_type_for(ext))
    return {
        "storage_path": result["path"],
        "ext": ext,
        "size": int(result.get("size") or len(data)),
        "filename": f"{_safe(document_id)}.{ext}",
    }


def find_existing(doc: dict) -> Optional[dict]:
    """Return the {storage_path, ext, size, filename} record embedded on the document."""
    return (doc or {}).get("audio_upload")


def fetch_bytes(storage_path: str) -> bytes:
    data, _ = get_object(storage_path)
    return data


def delete_existing(doc: dict) -> bool:
    """
    Object Storage has no delete API — soft-delete by signalling the caller
    to clear the document's `audio_upload` reference.
    Returns True if an audio upload was recorded.
    """
    return bool((doc or {}).get("audio_upload"))
