"""Encrypted Lulu credentials and OAuth connectivity helpers."""
import os

from cryptography.fernet import Fernet, InvalidToken
import httpx


class LuluIntegrationError(Exception):
    pass


def _fernet() -> Fernet:
    return Fernet(os.environ["INTEGRATION_CREDENTIALS_KEY"].encode("utf-8"))


def encrypt_credential(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_credential(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise LuluIntegrationError("Stored Lulu credentials cannot be decrypted.") from exc


def credential_hint(value: str) -> str:
    clean = value.strip()
    return f"••••{clean[-4:]}" if len(clean) >= 4 else "••••"


def lulu_urls(environment: str) -> tuple[str, str]:
    normalized = environment.strip().lower()
    if normalized not in {"sandbox", "production"}:
        raise LuluIntegrationError("Lulu environment must be sandbox or production.")
    prefix = f"LULU_{normalized.upper()}"
    return os.environ[f"{prefix}_API_BASE_URL"], os.environ[f"{prefix}_TOKEN_URL"]


async def verify_lulu_credentials(
    *,
    environment: str,
    client_key: str,
    client_secret: str,
) -> dict:
    api_base_url, token_url = lulu_urls(environment)
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=httpx.BasicAuth(client_key, client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.RequestError as exc:
        raise LuluIntegrationError("Could not reach Lulu. Try again shortly.") from exc
    if response.status_code in {401, 403}:
        raise LuluIntegrationError("Lulu rejected the client key or client secret.")
    if response.status_code == 429:
        raise LuluIntegrationError("Lulu rate-limited the connection test. Try again shortly.")
    if response.status_code >= 400:
        raise LuluIntegrationError("Lulu authentication is temporarily unavailable.")
    payload = response.json()
    if not payload.get("access_token"):
        raise LuluIntegrationError("Lulu did not return an access token.")
    return {"connected": True, "environment": environment, "api_base_url": api_base_url}