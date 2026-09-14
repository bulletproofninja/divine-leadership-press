"""Encryption at rest for user-supplied provider credentials."""

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    secret = (os.environ.get("CREDENTIAL_ENCRYPTION_KEY") or os.environ.get("JWT_SECRET") or "").strip()
    if len(secret) < 32:
        raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY or JWT_SECRET must contain at least 32 characters.")
    derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(derived)


def encrypt_secret(value: str) -> str:
    plain = (value or "").strip()
    if not plain or plain.startswith(PREFIX):
        return plain
    return PREFIX + _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    stored = (value or "").strip()
    if not stored:
        return None
    if not stored.startswith(PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored credential could not be decrypted.") from exc
