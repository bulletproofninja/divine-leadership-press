# DLP Test Credentials

## Owner / Super-Admin
- **Email**: carlos@divinepublisher.com
- **Password**: Not stored in source control. Use **Forgot password** on the login screen.
- **Name**: Carlos Callahan
- **Role**: Super Admin (can access /admin/affiliate, configure program parameters)
- **Security**: Password reset and password change invalidate all prior sessions.

## Affiliate Program (seeded)
- Reward type: cash_and_perks
- Signup commission: 30%
- MRR commission: 10%
- Active days required: 60
- Payout method: stripe_connect (NOT yet onboarded — config-only)
- Currency: USD

## Authentication test guidance
- Regular author accounts: register fresh on the fly with any `TEST_*` email.
- Do not store privileged passwords in this repository or test reports.
- Password recovery: `POST /api/auth/forgot-password` → emailed single-use link.
- Password reset: `POST /api/auth/reset-password`.
- Authenticated password change: `PUT /api/auth/change-password`.
