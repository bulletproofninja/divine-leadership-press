"""Password recovery primitives and Resend email delivery."""
import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import html
import os
import re
from urllib.parse import urlencode

import resend


RESET_TOKEN_TTL_MINUTES = 30
RESET_REQUEST_WINDOW_MINUTES = 15
RESET_REQUEST_LIMIT = 3
LOGIN_LOCK_MINUTES = 15
LOGIN_FAILURE_LIMIT = 5


def validate_new_password(password: str) -> None:
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Password must be between 12 and 128 characters.")
    checks = (
        (re.search(r"[a-z]", password), "one lowercase letter"),
        (re.search(r"[A-Z]", password), "one uppercase letter"),
        (re.search(r"\d", password), "one number"),
        (re.search(r"[^A-Za-z0-9]", password), "one symbol"),
    )
    missing = [label for match, label in checks if not match]
    if missing:
        raise ValueError(f"Password must include {', '.join(missing)}.")


def _pepper() -> bytes:
    return os.environ["PASSWORD_RESET_PEPPER"].encode("utf-8")


def hash_reset_token(token: str) -> str:
    return hmac.new(_pepper(), token.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_rate_limit_key(value: str) -> str:
    return hmac.new(_pepper(), value.encode("utf-8"), hashlib.sha256).hexdigest()


async def send_password_reset_email(recipient: str, token: str) -> str:
    resend.api_key = os.environ["RESEND_API_KEY"]
    sender = os.environ["RESEND_FROM_EMAIL"]
    frontend_url = os.environ["FRONTEND_URL"].rstrip("/")
    reset_url = f"{frontend_url}/reset-password?{urlencode({'token': token})}"
    safe_recipient = html.escape(recipient)
    safe_url = html.escape(reset_url, quote=True)
    params = {
        "from": f"Divine Leadership Press Security <{sender}>",
        "to": [recipient],
        "subject": "Reset your Divine Leadership Press password",
        "html": f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f7f4ec;padding:32px 16px;font-family:Arial,sans-serif;color:#062a4d">
          <tr><td align="center">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #d9d4c8;padding:32px">
              <tr><td style="font-family:Georgia,serif;font-size:24px;font-weight:bold;padding-bottom:16px">Divine Leadership Press</td></tr>
              <tr><td style="font-size:16px;line-height:1.6;padding-bottom:12px">A password reset was requested for {safe_recipient}.</td></tr>
              <tr><td style="font-size:14px;line-height:1.6;padding-bottom:24px">This secure link expires in {RESET_TOKEN_TTL_MINUTES} minutes and can be used once.</td></tr>
              <tr><td><a href="{safe_url}" style="display:inline-block;background:#062a4d;color:#ffffff;text-decoration:none;padding:12px 20px">Reset password</a></td></tr>
              <tr><td style="font-size:12px;line-height:1.5;color:#5d6670;padding-top:24px">If you did not request this, you can ignore this email. Your password will not change.</td></tr>
            </table>
          </td></tr>
        </table>
        """,
        "text": (
            "Reset your Divine Leadership Press password\n\n"
            f"Use this secure link within {RESET_TOKEN_TTL_MINUTES} minutes:\n{reset_url}\n\n"
            "If you did not request this, ignore this email."
        ),
    }
    response = await asyncio.to_thread(resend.Emails.send, params)
    return str(response.get("id") or "")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)