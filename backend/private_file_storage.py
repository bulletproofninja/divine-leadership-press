"""Private document-file storage helpers backed by Emergent Object Storage."""
from datetime import datetime, timezone
import re
from typing import Optional
import uuid

from object_storage import APP_NAME, get_object, put_object


MAX_MANUSCRIPT_BYTES = 25 * 1024 * 1024


def _safe_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value or "")


def safe_download_name(filename: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "file").strip("._")
    return base[:180] or "file"


def manuscript_content_type(filename: str) -> str:
    if (filename or "").lower().endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "text/plain; charset=utf-8"


def build_private_file_record(
    *,
    user_id: str,
    document_id: str,
    category: str,
    variant: str,
    filename: str,
    content_type: str,
    size_bytes: int,
    storage_path: str,
    record_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": record_id or str(uuid.uuid4()),
        "user_id": user_id,
        "document_id": document_id,
        "category": category,
        "variant": variant,
        "filename": safe_download_name(filename),
        "content_type": content_type or "application/octet-stream",
        "size_bytes": int(size_bytes),
        "storage_path": storage_path,
        "is_deleted": False,
        "created_at": created_at or now,
        "updated_at": now,
    }


def store_private_file(
    *,
    user_id: str,
    document_id: str,
    category: str,
    variant: str,
    filename: str,
    data: bytes,
    content_type: str,
    storage_path: Optional[str] = None,
    record_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> dict:
    if not data:
        raise ValueError("File is empty.")
    safe_filename = safe_download_name(filename)
    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else "bin"
    path = storage_path or (
        f"{APP_NAME}/documents/{_safe_segment(user_id)}/{_safe_segment(document_id)}/"
        f"{_safe_segment(category)}/{uuid.uuid4()}.{_safe_segment(ext)}"
    )
    result = put_object(path, data, content_type or "application/octet-stream")
    return build_private_file_record(
        user_id=user_id,
        document_id=document_id,
        category=category,
        variant=variant,
        filename=safe_filename,
        content_type=content_type,
        size_bytes=int(result.get("size") or len(data)),
        storage_path=result["path"],
        record_id=record_id,
        created_at=created_at,
    )


def fetch_private_file(storage_path: str):
    return get_object(storage_path)