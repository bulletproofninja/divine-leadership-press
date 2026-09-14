# Authentication Testing Playbook

## Security invariants
- Never store or print plaintext privileged passwords or reset tokens.
- Password-reset tokens are random, single-use, expire after 30 minutes, and are stored only as HMAC-SHA256 hashes.
- Password reset/change increments `users.token_version`; all older JWTs must return HTTP 401.
- Forgot-password responses are identical for existing and unknown email addresses.
- Five failed sign-in attempts produce a 15-minute lockout.
- Privileged credentials must come from secure runtime configuration, never repository files.

## Required verification
1. Run `/app/backend/tests/test_password_recovery.py`.
2. Verify MongoDB indexes on `users.email`, `password_reset_tokens.token_hash`, and TTL indexes on reset/rate-limit collections.
3. Verify the login modal's Forgot Password flow at desktop and mobile widths.
4. Verify `/reset-password?token=...` accepts a strong password, rejects weak/reused/expired tokens, and returns users to sign-in.
5. Verify Settings → Password & sessions changes a password and signs out the current session.
6. Verify no plaintext owner password appears outside `.git` history.

## Resend
- Required runtime variables: `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `FRONTEND_URL`, `PASSWORD_RESET_PEPPER`, `JWT_SECRET`.
- `divinepublisher.com` must show **Verified** in Resend before `security@divinepublisher.com` can deliver production reset emails.