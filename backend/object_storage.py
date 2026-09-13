"""
Emergent Object Storage helpers.

Replaces local disk uploads (open()/write_bytes) so the app can be deployed
to environments where the pod filesystem is ephemeral.
"""
import logging
import os
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

APP_NAME = os.environ.get("STORAGE_APP_PREFIX", "dlp")

_storage_key: Optional[str] = None


def _storage_url() -> str:
    base = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip()
    if not base:
        base = "https://integrations.emergentagent.com"
    return base.rstrip("/") + "/objstore/api/v1/storage"


def init_storage(force: bool = False) -> str:
    """Mint (or reuse) a session-scoped storage key. Call once at startup."""
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    key_env = os.environ.get("EMERGENT_LLM_KEY")
    if not key_env:
        raise RuntimeError("EMERGENT_LLM_KEY is not set; object storage cannot init.")
    resp = requests.post(
        f"{_storage_url()}/init",
        json={"emergent_key": key_env},
        timeout=30,
    )
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    logger.info("Emergent Object Storage initialised.")
    return _storage_key


def _do(method: str, path: str, **kwargs):
    key = init_storage()
    headers = kwargs.pop("headers", {}) or {}
    headers["X-Storage-Key"] = key
    url = f"{_storage_url()}/objects/{path}"
    resp = requests.request(method, url, headers=headers, **kwargs)
    if resp.status_code == 404:
        # Cached key may be stale; refresh once and retry (per playbook).
        headers["X-Storage-Key"] = init_storage(force=True)
        resp = requests.request(method, url, headers=headers, **kwargs)
    return resp


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload bytes. Returns {'path', 'size', 'etag'}."""
    resp = _do(
        "PUT",
        path,
        headers={"Content-Type": content_type},
        data=data,
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> Tuple[bytes, str]:
    """Download bytes. Returns (content, content_type)."""
    resp = _do("GET", path, timeout=90)
    resp.raise_for_status()
    return resp.content, resp.headers.get(
        "Content-Type", "application/octet-stream"
    )
