"""Encrypted Lulu credentials and OAuth connectivity helpers."""
import os

import httpx

from secrets_vault import decrypt_secret, encrypt_secret


LULU_URLS = {
    "production": (
        "https://api.lulu.com",
        "https://api.lulu.com/auth/realms/glasstree/protocol/openid-connect/token",
    ),
    "sandbox": (
        "https://api.sandbox.lulu.com",
        "https://api.sandbox.lulu.com/auth/realms/glasstree/protocol/openid-connect/token",
    ),
}


class LuluIntegrationError(Exception):
    pass


def encrypt_credential(value: str) -> str:
    return encrypt_secret(value)


def decrypt_credential(value: str) -> str:
    try:
        decrypted = decrypt_secret(value)
        if not decrypted:
            raise RuntimeError("Credential is empty.")
        return decrypted
    except RuntimeError as exc:
        raise LuluIntegrationError("Stored Lulu credentials cannot be decrypted.") from exc


def credential_hint(value: str) -> str:
    clean = value.strip()
    return f"••••{clean[-4:]}" if len(clean) >= 4 else "••••"


def lulu_urls(environment: str) -> tuple[str, str]:
    normalized = environment.strip().lower()
    if normalized not in {"sandbox", "production"}:
        raise LuluIntegrationError("Lulu environment must be sandbox or production.")
    prefix = f"LULU_{normalized.upper()}"
    default_api_url, default_token_url = LULU_URLS[normalized]
    return (
        os.environ.get(f"{prefix}_API_BASE_URL", default_api_url).rstrip("/"),
        os.environ.get(f"{prefix}_TOKEN_URL", default_token_url),
    )


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
    try:
        payload = response.json()
    except ValueError as exc:
        raise LuluIntegrationError("Lulu returned an invalid authentication response.") from exc
    if not payload.get("access_token"):
        raise LuluIntegrationError("Lulu did not return an access token.")
    return {"connected": True, "environment": environment.strip().lower(), "api_base_url": api_base_url}
