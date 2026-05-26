"""
Cover image uploads — store per-user, per-document cover art on disk.
"""
import os
import re
from pathlib import Path
from typing import Optional, Tuple

UPLOAD_ROOT = Path(os.environ.get("COVER_UPLOAD_DIR", "/app/backend/uploads/covers"))

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _safe_ext(filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return ext if ext in ALLOWED_EXTENSIONS else ""


def _user_dir(user_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", user_id)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    d = UPLOAD_ROOT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def storage_path(user_id: str, document_id: str, ext: str) -> Path:
    safe_doc = re.sub(r"[^A-Za-z0-9_-]", "_", document_id)
    return _user_dir(user_id) / f"{safe_doc}.{ext}"


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


def save_upload(user_id: str, document_id: str, filename: str, data: bytes) -> Tuple[Path, str]:
    ext = _safe_ext(filename)
    if not ext:
        raise ValueError(
            f"Unsupported image format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Cover image too large. Maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if len(data) < 64:
        raise ValueError("File appears to be empty.")
    existing = find_existing(user_id, document_id)
    if existing:
        try:
            existing[0].unlink()
        except FileNotFoundError:
            pass
    path = storage_path(user_id, document_id, ext)
    path.write_bytes(data)
    return path, ext


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
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")
