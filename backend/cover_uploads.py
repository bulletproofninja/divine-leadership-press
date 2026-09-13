"""
Cover image uploads — per-user, per-document cover art stored in Emergent Object Storage.

Metadata is kept on the parent `documents` record under `cover_upload`:
    {"storage_path": str, "ext": str, "size": int, "filename": str}
"""
import re
from typing import Optional

from object_storage import APP_NAME, get_object, put_object

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", s or "")


def _safe_ext(filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return ext if ext in ALLOWED_EXTENSIONS else ""


def media_type_for(ext: str) -> str:
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def save_upload(user_id: str, document_id: str, filename: str, data: bytes) -> dict:
    ext = _safe_ext(filename)
    if not ext:
        raise ValueError(
            f"Unsupported image format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Cover image too large. Maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    if len(data) < 64:
        raise ValueError("File appears to be empty.")
    path = f"{APP_NAME}/covers/{_safe(user_id)}/{_safe(document_id)}.{ext}"
    result = put_object(path, data, media_type_for(ext))
    return {
        "storage_path": result["path"],
        "ext": ext,
        "size": int(result.get("size") or len(data)),
        "filename": f"{_safe(document_id)}.{ext}",
    }


def find_existing(doc: dict) -> Optional[dict]:
    return (doc or {}).get("cover_upload")


def fetch_bytes(storage_path: str) -> bytes:
    data, _ = get_object(storage_path)
    return data


def delete_existing(doc: dict) -> bool:
    return bool((doc or {}).get("cover_upload"))
