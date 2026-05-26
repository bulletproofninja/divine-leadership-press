"""
Audio uploads — store author-supplied MP3 audiobook files on disk and
serve them back through authenticated endpoints.
"""
import os
import re
from pathlib import Path
from typing import Optional, Tuple

UPLOAD_ROOT = Path(os.environ.get("AUDIO_UPLOAD_DIR", "/app/backend/uploads/audio"))

ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "ogg", "flac"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


def _safe_ext(filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return ext if ext in ALLOWED_EXTENSIONS else ""


def storage_path(user_id: str, document_id: str, ext: str) -> Path:
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", user_id)
    safe_doc = re.sub(r"[^A-Za-z0-9_-]", "_", document_id)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    user_dir = UPLOAD_ROOT / safe_user
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / f"{safe_doc}.{ext}"


def find_existing(user_id: str, document_id: str) -> Optional[Tuple[Path, str]]:
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", user_id)
    safe_doc = re.sub(r"[^A-Za-z0-9_-]", "_", document_id)
    user_dir = UPLOAD_ROOT / safe_user
    if not user_dir.exists():
        return None
    for ext in ALLOWED_EXTENSIONS:
        p = user_dir / f"{safe_doc}.{ext}"
        if p.exists():
            return p, ext
    return None


def save_upload(user_id: str, document_id: str, filename: str, data: bytes) -> Path:
    ext = _safe_ext(filename)
    if not ext:
        raise ValueError(
            f"Unsupported audio format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large. Maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if len(data) < 64:
        raise ValueError("File appears to be empty.")
    # Remove any previous audio for this document
    existing = find_existing(user_id, document_id)
    if existing:
        try:
            existing[0].unlink()
        except FileNotFoundError:
            pass
    path = storage_path(user_id, document_id, ext)
    path.write_bytes(data)
    return path


def delete_existing(user_id: str, document_id: str) -> bool:
    existing = find_existing(user_id, document_id)
    if not existing:
        return False
    try:
        existing[0].unlink()
    except FileNotFoundError:
        return False
    return True


def media_type_for(ext: str) -> str:
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
    }.get(ext, "application/octet-stream")
