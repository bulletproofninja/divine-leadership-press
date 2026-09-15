# Divine Leadership Press — PRD

## Original Problem Statement
A book publishing / writing application that allows users to upload a Word doc, text file, or Pages file. It must auto-convert and format to publishing types (6×9, ePub, magazine) with full editorial capabilities and a professional aesthetic ("100-year-old book publishing company"). App name: **Divine Leadership Press**. Must support export for Amazon KDP, Lulu, etc. Branding: Navy Blue & Cream from uploaded logo.

## User Personas
- Independent authors preparing manuscripts for KDP/Lulu
- Editors managing manuscripts with version history & comments
- Magazine/long-form writers needing 8.5×11 layouts

## Core Requirements (locked)
- Auth (register/login) + per-user document workspace
- Rich text editor (ReactQuill) with versioning & comments
- Upload `.docx` / `.txt` (Pages → instruct user to export as .docx first)
- Export to real PDF at **all standard KDP trim sizes** + ePub
- Navy-blue / cream classic publishing aesthetic

## Project Export (2026-09-13)
- [x] Created a complete downloadable source archive containing the current frontend, backend, assets, dependency manifests, configuration files, tests, and documentation.
- [x] Included `.gitignore` and GitHub-facing project files while excluding `.git/` repository history, `.emergent/` internals, dependencies, build output, and caches.
- [x] Included sanitized backend/frontend `.env` files with key names preserved and values blank; removed test credentials and scanned the archive for common secret/token patterns.

## Security Incident Response & Password Recovery (2026-09-14)
- [x] Rotated the exposed owner password to an unshared random value, changed the owner email to `carlos@divinepublisher.com`, rotated the JWT signing secret, incremented the owner token version, and invalidated all prior sessions.
- [x] Demoted eight disposable `TEST_*` accounts that had accumulated super-admin privileges; exactly one super-admin remains.
- [x] Removed plaintext privileged credentials from current source files, test suites, test reports, and `/app/memory/test_credentials.md`.
- [x] Added enumeration-safe `POST /api/auth/forgot-password`, 15-minute request throttling, HMAC-SHA256 reset-token hashes, 30-minute expiry, one-time consumption, and TTL indexes.
- [x] Added `POST /api/auth/reset-password` and authenticated `PUT /api/auth/change-password` with a 12–128 character complexity policy and session invalidation.
- [x] Added five-attempt / 15-minute login lockout and cleared failure counters after successful login.
- [x] Added `HttpOnly`, `Secure`, `SameSite=Lax` auth cookies while preserving bearer-token compatibility; logout/reset/change clear the cookie.
- [x] Removed the hardcoded JWT fallback. `JWT_SECRET`, `PASSWORD_RESET_PEPPER`, and `RESEND_API_KEY` are stored only in ignored runtime configuration.
- [x] Locked CORS to explicit origins and normalized the trusted preview edge's rewritten Origin using its forwarded public host.
- [x] Added Forgot Password login UI, public `/reset-password` route, and Settings → Password & sessions controls.
- [x] Emergency single-use owner reset email successfully delivered to `security@divinepublisher.com` without exposing its token.
- [x] Verification: 18/18 auth hardening tests passed, frontend production build passed, credential scan passed, and desktop/mobile overflow checks passed.
- [ ] **External blocker:** verify `divinepublisher.com` at https://resend.com/domains before normal emails can send from `security@divinepublisher.com`.
- [ ] GitHub history may retain the now-invalid historical credential even though current files are clean. Purge affected historical commits through GitHub's secret-removal workflow after saving this secure checkpoint.

## Lulu Production Credential Vault (2026-09-15)
- [x] Added a **super-admin-only Lulu Direct** panel to Settings with Production selected by default, optional Sandbox switching, client key/secret fields, and production charge warning.
- [x] Added encrypted credential persistence using a Fernet key stored only in ignored runtime configuration. MongoDB stores ciphertext and a masked client-key hint; plaintext/ciphertext are never returned to the browser.
- [x] Added owner-only APIs: `GET/PUT/DELETE /api/admin/integrations/lulu` and `POST /api/admin/integrations/lulu/test`.
- [x] Added real Lulu OAuth `client_credentials` connectivity testing using HTTP Basic authentication, bounded timeouts, environment-based URLs, and safe non-leaky errors.
- [x] Replacing credentials updates one unique provider/owner row; clear requires explicit confirmation in the UI.
- [x] Fixed asynchronous status loading so a fast Sandbox selection cannot be overwritten by the initial Production response; selector exposes accessible active state.
- [x] Verification: 18/18 final Lulu/auth/storage regressions passed, frontend production build passed, desktop/mobile overflow checks passed, and ignored-secret scan passed.
- [ ] **User action:** enter the real Lulu production client key/secret in Settings → Lulu Direct, save, then click **Test connection**.
- [ ] **Not yet implemented:** real Lulu cost calculation, file-validation handoff, print-job submission, status tracking, and webhooks. The pre-existing Lulu publish action remains **MOCKED** until this next phase.

## Implemented (2026-09-13) — PRIVATE FILE & MEDIA STORAGE
- [x] Extended Emergent Object Storage to retain original `.docx` / `.txt` manuscript uploads, generated print PDFs, ePub files, cover PDFs, OpenAI/ElevenLabs audiobooks, and per-chapter audiobook ZIPs.
- [x] Added MongoDB `document_files` registry with owner/document scope, canonical storage paths, MIME types, sizes, variants, timestamps, and soft-delete status.
- [x] Added private authenticated file APIs: `GET /api/documents/{id}/files` and `GET /api/documents/{id}/files/{file_id}`. Storage paths and user IDs are never exposed; cross-user access returns 404.
- [x] Existing cover, uploaded audiobook, and voice-memo objects are registered/backfilled into the same private vault without duplicating their stored bytes.
- [x] Regenerating the same export variant overwrites its canonical object and reuses its file record to prevent duplicate active records.
- [x] Added the Editor **Private File Vault** with filename/type/size details, refresh, and authenticated downloads. Verified without horizontal overflow at 1920×800 and 390×844.
- [x] Transient read-aloud previews and dictation chunks remain intentionally unretained; only durable manuscript/media assets are stored.
- [x] Testing: private-storage suite 4/4, iteration-20 suite 3/3, storage regressions 66 passed / 1 skipped, post-audit harness regressions 44 passed / 1 skipped, and frontend production build passed.


## Implemented (as of 2026-02-13) — EMERGENT OBJECT STORAGE MIGRATION (P0 deploy blocker resolved)
- [x] All file uploads (book covers, audiobook MP3s, per-paragraph voice memos) migrated from ephemeral pod disk to **Emergent Object Storage**.
- [x] New `/app/backend/object_storage.py` — thin wrapper around `INTEGRATION_PROXY_URL /objstore/api/v1/storage` (init/put/get) with stale-key auto-refresh.
- [x] Refactored `audio_uploads.py`, `cover_uploads.py`, `voice_memos.py`: no more `path.write_bytes(...)`. Metadata (storage_path, ext, size, filename) stored inline on the parent document (`audio_upload`, `cover_upload`, `memos[].storage_path`).
- [x] Server startup calls `init_object_storage()`; deletes are soft (clears the doc reference) since Object Storage has no DELETE API.
- [x] Verified end-to-end via curl (cover, audio, memos: upload → info → fetch → delete) and the full existing pytest suite (30 passed / 1 skipped).

## Pending (next up)
- [ ] Add **OpenAI-compatible custom endpoint URL** (Ollama / Groq / LM Studio) to the BYO-key matrix in `/settings` — user asked for Ollama support; only OpenAI + Anthropic BYO keys are exposed today.

## Implemented (as of 2026-02-28) — AGENT QUOTA / PAYWALL
- [x] **Writing agent locked behind Author Pro plan**:
  - Free users: 5 agent messages/day (chat + Cmd-K combined). Resets at UTC midnight.
  - Active subscribers (any plan): unlimited.
  - New `/api/ai/agent/quota` endpoint returns `{unlimited|used|limit|remaining}` for the UI.
  - Chat + Command endpoints return 402 with `code: "agent_quota_exceeded"` when over limit. Both also include a `quota` block in their success responses so the UI can decrement live.
  - New `/app/backend/agent_quota.py` module; new `agent_usage` collection (one doc per user per UTC day, atomic `$inc`).
- [x] **Frontend lock UX**:
  - Quota pill in the agent header: `3/5 free today` (amber when ≤1 left), or `Unlimited` (emerald) for subscribers.
  - Full-panel upgrade overlay in `WritingAgentPanel` when quota is exhausted: "You're out of free agent messages today" → "See plans — $19/mo" button → `/billing`.
  - Same lock card inside `InlineCommandBar` (Cmd-K) so the upsell appears anywhere the agent is invoked.
  - Pre-flight check: if quota is already at 0 on send, we skip the API call and go straight to the upsell.

## Implemented (as of 2026-02-28) — AI WRITING AGENT
- [x] **Conversational writing agent** (`/api/ai/agent/chat`): per-document, per-session persistent chat with Claude Sonnet 4.5. Knows the current manuscript (truncated to ~12k chars) and prior turns (last 20). Voice presets: match_my_voice (default — samples middle of doc), literary, journalistic, conversational, formal_business, poetic, scholarly.
- [x] **Inline Cmd-K command bar** (`/api/ai/agent/command`): highlight passage → press Ctrl/Cmd-K → type instruction or click a quick chip → preview rewrite → Accept (replaces selection) / Reject / Retry.
- [x] Backend: new `/app/backend/writing_agent.py` module + endpoints `/ai/agent/voices`, `/ai/agent/chat`, `/ai/agent/history/{id}` (GET + DELETE), `/ai/agent/command`. New collection `agent_sessions` for history. Imports from existing `emergentintegrations.llm.chat` (no new keys).
- [x] Frontend: two new components — `/app/frontend/src/components/WritingAgentPanel.js` (right-bottom floating chat with starter chips, voice picker, Insert / Replace selection / Copy actions on assistant messages) and `InlineCommandBar.js` (modal Cmd-K dialog with quick-command chips + diff-style preview). New "Agent" button in the editor header next to Save. Persistent floating ⌘K hint in the bottom-left when the agent is closed. Lint clean.

## Implemented (as of 2026-02-28) — LIVE STRIPE + CONNECT WIRED UP
- [x] **Auto-paying affiliates via Stripe Connect (Express)**:
  - `subscription_billing.py` extended with `create_express_account`, `create_onboarding_link`, `create_express_login_link`, `retrieve_account_status`, `create_transfer`.
  - New endpoints:
    - `POST /api/affiliate/connect/onboard` → creates Express account (if needed) + mints Stripe-hosted onboarding URL
    - `GET /api/affiliate/connect/status` → returns charges_enabled / payouts_enabled / requirements_due
    - `POST /api/affiliate/connect/dashboard-link` → SSO link into Stripe Express dashboard
    - `POST /api/admin/commissions/auto-payout` → batch Stripe Transfer per pending commission with per-row failure reasons
  - User model: added `stripe_connect_account_id`. Commissions: now persist `stripe_transfer_id` + `payout_method='stripe_connect'`.
  - Frontend:
    - HelpPage Earnings card now opens with **"Connect your payout account to get paid automatically — Stripe Express, 2-minute setup"** with a Connect-with-Stripe button. After onboarding, shows "Payout account connected" + Stripe dashboard SSO link.
    - New `/affiliate/connect/return` and `/affiliate/connect/refresh` routes for Stripe's redirect handlers.
    - AdminCommissionsPage: new **"Auto-pay via Stripe"** button next to "Mark as paid" — sends Transfers in batch, shows failure reasons inline (no_connect_account / account_not_ready / requirements_due / stripe errors).
  - Graceful degradation: if Connect isn't enabled on the platform account yet, onboarding returns HTTP 503 with a clear "owner must enable at dashboard.stripe.com/connect" message — surfaces directly to the affiliate as a toast.

## ⚠️ Pending owner action to make auto-payouts FULLY work
- **Enable Stripe Connect on your platform account** (5-min one-time setup):
  1. Stripe Dashboard → **Connect** → "Get started"
  2. Choose **Platform or marketplace**
  3. Fill out the Platform Profile (business name, support email, brand colours)
  4. That's it — no code changes needed; the affiliate "Connect with Stripe" button will start working immediately.
- After at least one affiliate has onboarded and earned a commission, you can batch-pay them all in one click at `/admin/commissions` → "Auto-pay via Stripe".

## Implemented (as of 2026-02-28) — LIVE STRIPE WIRED UP
- [x] **True recurring subscriptions** using owner's LIVE Stripe account (`acct_1T9pykLv0zc3PRer`, `besthustlemindset@gmail.com`):
  - Raw `stripe` Python SDK (v14.4.1) added; new `/app/backend/subscription_billing.py` module.
  - Products + recurring monthly Prices auto-created in Stripe on first checkout (idempotent via `metadata.dlp_plan_id`).
  - `mode=subscription` Checkout sessions; Stripe auto-charges every 30 days.
  - `/api/billing/portal` opens Stripe **Customer Portal** so subscribers can update card / cancel.
  - `/api/billing/diagnostics` reports `subscription_billing_configured`, `live_mode`, `webhook_secret_configured`.
  - Frontend: LIVE-mode banner on `/billing`, "Manage subscription" button when active.
  - Webhook handler now processes:
    - `checkout.session.completed` → first payment, captures `stripe_customer_id` + `stripe_subscription_id` on the user
    - `invoice.paid` (billing_reason=`subscription_cycle`) → renewal credits + MRR commission (idempotent per invoice.id)
    - `customer.subscription.deleted` → marks sub inactive
    - `customer.subscription.updated` → tracks `cancel_at_period_end`
  - User model: added `stripe_customer_id` field.
  - Subscriptions collection: now stores `stripe_subscription_id`, `stripe_customer_id`, `stripe_status`, `cancel_at_period_end`.
- [x] Backward-compatible: when `STRIPE_SECRET_KEY` is missing, falls back to the original emergentintegrations test-key one-time-payment flow.
- [x] All 34 billing tests + 14 iter15 regression tests still pass.

## ⚠️ Pending owner action to make live subscriptions FULLY work
- **STRIPE_WEBHOOK_SECRET** must be set. Without it, recurring monthly renewals won't be auto-credited (the initial subscribe still works because the success page polls the session status).
- Steps the owner needs to do:
  1. Stripe Dashboard → Developers → Webhooks → "Add endpoint"
  2. URL: `https://editorial-studio-19.preview.emergentagent.com/api/webhook/stripe`
  3. Listen for: `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`, `customer.subscription.updated`
  4. Reveal "Signing secret" (`whsec_...`) and paste it into `STRIPE_WEBHOOK_SECRET` in `/app/backend/.env`
  5. `sudo supervisorctl restart backend`

## Implemented (as of 2026-02-27)
- [x] **Stripe Subscription Billing** (via emergentintegrations Stripe Checkout wrapper with STRIPE_API_KEY=sk_test_emergent):
  - 2 plans defined server-side: **Author Pro** ($19/mo) and **Estate** ($49/mo); each payment grants 30 days of access (extends `pro_until` on the user's `subscriptions` doc).
  - `POST /api/billing/checkout` creates a fixed-amount Stripe Checkout session and inserts a `payment_transactions` row.
  - `GET /api/billing/checkout/status/{session_id}` polls Stripe and idempotently credits the subscription + accrues affiliate commission.
  - `POST /api/webhook/stripe` receives webhook events (signature-verified by the SDK) and credits the same way (defense-in-depth on user_id — trusts the server-side txn over Stripe metadata).
  - `GET /api/billing/plans` (public) and `GET /api/billing/me` (auth) expose the catalogue and the user's current subscription state.
- [x] **Affiliate commissions ledger** (`commissions` collection):
  - On every paid checkout, if the referee was referred by someone, accrue a commission per `affiliate_settings`: signup% on first payment; mrr% on every subsequent payment within `active_days_required` (default 60) of signup.
  - `GET /api/billing/commissions` — current user's earnings ledger + pending/paid totals.
  - `GET /api/admin/commissions` — super-admin only; lists all commissions + pending balances per affiliate.
  - `POST /api/admin/commissions/mark-paid` — super-admin only; marks N rows paid with payout_method (manual/stripe_connect/paypal/wire) + reference.
- [x] **Frontend billing UX**:
  - `/billing` plan picker page with Stripe redirect on subscribe.
  - `/billing/success` polls the session status (max 10 attempts, 2s interval) until paid/expired.
  - `/admin/commissions` payout dashboard with select-rows-and-mark-paid flow.
  - Earnings card surfaced in `/help` Share & Refer footer (pending + paid + ledger).
  - Dashboard header: new "Plans" link for everyone; "Admin" + "Payouts" for owner.
- [x] **Per-chapter audiobook export**:
  - `GET /api/documents/{id}/audiobook/chapters/preview` — H1/H2-split chapter list with word counts.
  - `POST /api/documents/{id}/audiobook/chapters` — returns ZIP of one MP3 per chapter + tracklist.txt (uses OpenAI TTS via existing pipeline).
  - "Per-chapter audiobook" panel in the Editor's Audio Studio with Detect / Export ZIP buttons + collapsible chapter preview list.
- [x] Backend pytest: +34 tests in `/app/backend/tests/test_billing.py` (covers plans, checkout creation, status polling, idempotency, commission accrual, admin payouts, chapter-export validation paths). Total backend tests now: 147 (113 existing + 34 new).

## Implemented (as of 2026-02-26)
- [x] Auth (JWT) + user dashboard + document CRUD
- [x] Landing page, dashboard, editor (Quill) with version & comment panels
- [x] Brand theme (Navy Blue / Cream) + logo
- [x] **Upload `.docx`** → HTML preserving headings, bold, italic, underline, lists, alignment
- [x] **Upload `.txt`** → paragraph-aware HTML
- [x] **`.pages` rejection** with explicit "export to .docx first" instructional toast
- [x] **Real PDF export** (reportlab) at all 12 KDP trim sizes (5×8 → 8.5×11) with title page, page numbers, mirrored margins
- [x] **Real ePub export** (ebooklib) with H1-based chapter splitting + serif CSS
- [x] `/api/export/formats` endpoint + trim-size dropdown in editor
- [x] **AI Editorial Polish** powered by Claude Sonnet 4.5 (via Emergent universal key):
  - Tighten Prose, Improve Clarity, Back-Cover Blurb, Suggest Chapter Titles, Generate Synopsis
  - Apply / Copy / Discard preview flow in editor sidebar
- [x] **Editor's Desk — Full Copy-Edit Pass** (Claude Sonnet 4.5, structured JSON output):
  - 11 issue categories: grammar, punctuation, spelling, run_on, comma_splice, passive, wordy, repetition, consistency, clarity, tone
  - 3 severity levels (must_fix / suggested / stylistic) with colour-coded badges
  - Per-issue Accept / Reject (HTML-level replace preserves inline formatting; text-walker fallback for cross-tag matches)
  - Accept All / Reject All / severity filter
  - Style-guide selector: Chicago Manual / AP / MLA / DLP House Style
  - Local readability metrics: Flesch-Kincaid grade, avg sentence length, passive %, adverb density, longest-sentence callout
- [x] **Audio Studio — Read Aloud + Audiobook MP3** (3 provider tabs):
  - **OpenAI TTS HD** (Emergent key): 9 voices, speed 0.5×–2.0×, in-browser preview, full audiobook MP3 download
  - **ElevenLabs** (per-user key in user profile): stock voice library + custom cloned Voice ID, preview, premium audiobook download
  - **Uploaded MP3**: author uploads a finished audio file (mp3/wav/m4a/ogg/flac, ≤200 MB), playable in-browser, removable
- [x] **Publication Pipeline Tracker** (6 steps: Manuscript → Metadata → Cover → PDF → ePub → Audiobook):
  - Dashboard cards render per-book pipeline badges with ✓/pending state
  - Editor sidebar shows live Pipeline Progress card (N/6) at the top
  - Server-side `_compute_pipeline_status` checks content length, metadata completeness, cover/audio uploads, and export timestamps
- [x] **Book Setup panel** in editor — Cover image upload (JPG/PNG/WebP ≤10 MB, with thumbnail preview), plus KDP metadata fields: Author, Subtitle, Description, ISBN, Language, Category, Keywords, Publisher
- [x] Dashboard cover thumbnails (replaces generic icon when a cover is uploaded)
- [x] **Cover → PDF converter** (reportlab + PIL): one-click "Download Cover as PDF" from Book Setup, sized to selected KDP trim; plus a generic `POST /api/tools/image-to-pdf` endpoint for any JPG/PNG/WebP
- [x] **Voice Dictation** (OpenAI Whisper via Emergent key): Dictate button in editor toolbar; MediaRecorder captures mic, sends to `/api/transcribe`, Whisper returns punctuated text, inserted at the Quill cursor position
- [x] **Continuous Dictation Mode**: Switch toggle next to Dictate button — records in 30-second segments, transcribing each as it completes; pulsing red recording indicator inside the Dictation History panel
- [x] **Dictation History panel** in editor sidebar: shows each transcribed chunk (timestamp + text) with per-chunk Undo (search-and-remove from manuscript) and Clear All buttons; renders only when history > 0
- [x] **Voice Memos** (per-paragraph audio annotations):
  - Record raw audio notes anchored to the cursor's current paragraph (auto-detected via Quill block index)
  - List/play/transcribe-and-insert/delete per memo
  - Transcripts cached after first Whisper call (subsequent inserts re-use cached text)
  - Storage: private bytes in Emergent Object Storage, metadata in `document.memos` and the `document_files` registry
- [x] **Help & Documentation page** (`/help`, public route): 13 sections covering every major feature (Getting Started, Pipeline, Upload, Editor, Book Setup, Editor's Desk, AI Polish, Dictation, Voice Memos, Audio Studio, Export, Privacy, Tips). Sticky TOC sidebar, motion-animated section reveals, **bold** markdown rendering. Help links in Dashboard + Editor headers.
- [x] **Referral / Affiliate system**:
  - Every user gets an 8-char `referral_code` on registration
  - `?ref=CODE` URL param auto-opens the register tab and pre-fills the code
  - Optional code field on the register form
  - `GET /api/auth/me/referrals` returns code, total invited count, and recent invitee names (no emails leaked)
  - "Share & Refer" card in `/help` footer (authenticated users only) with copy-link, native share, and a recent-invitees list
  - Legacy backfill: any pre-existing user without a code gets one on next `/auth/me` call (Pydantic Optional + explicit set fix)
- [x] **Affiliate Leaderboard + Badges + Admin Foundation**:
  - Public **Top Inviters** leaderboard on `/help` (top 10 by referral count, ranked with amber/silver/bronze rank badges)
  - 4-tier badge system on each user: Ambassador (1+), Author Advocate (5+), Patron of Letters (10+), Founding Editor (25+) — displayed in the Share & Refer card
  - Super-admin role on User model + `/api/admin/affiliate/settings` (super-admin write-only) endpoint to configure: `reward_type` (credits/cash/perks/none), `commission_percent`, `minimum_payout`, `qualifying_event` (signup/first_paid_subscription/first_book_published), `reward_value`, `currency`, `notes`
  - Public `/api/affiliate/settings` so authors see program rules in their Share & Refer card
  - Default: tracking-only mode (no payout) until owner sets parameters
- [x] Backend pytest suites (113 tests, 100% pass):
  - `/app/backend/tests/test_upload_export.py` (14)
  - `/app/backend/tests/test_ai_editorial.py` (8)
  - `/app/backend/tests/test_copyedit.py` (11)
  - `/app/backend/tests/test_audio_studio.py` (11)
  - `/app/backend/tests/test_elevenlabs_upload.py` (22)
  - `/app/backend/tests/test_pipeline_cover.py` (17)
  - `/app/backend/tests/test_dictation_and_cover_pdf.py` (17)
  - `/app/backend/tests/test_voice_memos.py` (13)
  - `/app/backend/tests/test_upload_export.py` (14)
  - `/app/backend/tests/test_ai_editorial.py` (8)
  - `/app/backend/tests/test_copyedit.py` (11)
  - `/app/backend/tests/test_audio_studio.py` (11)
  - `/app/backend/tests/test_elevenlabs_upload.py` (22)
  - `/app/backend/tests/test_pipeline_cover.py` (17)
  - `/app/backend/tests/test_dictation_and_cover_pdf.py` (17)

## Architecture
```
/app/
├── backend/
│   ├── server.py          # FastAPI app: auth, documents, upload, export, AI, integrations
│   ├── auth_security.py   # Password policy, reset-token hashing, Resend delivery
│   ├── lulu_integration.py # Encrypted Lulu credentials + OAuth connectivity
│   ├── private_file_storage.py # Private manuscript/export/media object-storage helpers
│   ├── exporters.py       # KDP_TRIM_SIZES, docx_to_html, generate_pdf, generate_epub
│   ├── ai_editor.py       # Claude Sonnet 4.5 editorial tools (5 endpoints)
│   ├── tests/test_upload_export.py
│   ├── tests/test_ai_editorial.py
│   └── requirements.txt   # + reportlab, beautifulsoup4, ebooklib, python-docx, emergentintegrations
├── frontend/src/pages/
│   ├── LandingPage.js
│   ├── ResetPasswordPage.js # Public single-use password reset screen
│   ├── SettingsPage.js    # Passwords, BYO AI keys, Lulu Direct credentials
│   ├── Dashboard.js       # upload accepts .docx/.txt/.pages
│   └── EditorPage.js      # blob-download export, trim-size selector
```

## API Endpoints
- `POST /api/auth/register | /login | /logout | GET /api/auth/me`
- `POST /api/auth/forgot-password | /reset-password`
- `PUT /api/auth/change-password`
- `GET/PUT/DELETE /api/admin/integrations/lulu`
- `POST /api/admin/integrations/lulu/test`
- `GET|POST|PUT|DELETE /api/documents[/{id}]`
- `POST /api/documents/upload` (.docx, .txt; .pages → 400 with guidance)
- `GET /api/documents/{id}/files` → owner-scoped private file registry
- `GET /api/documents/{id}/files/{file_id}` → authenticated private download
- `GET /api/export/formats` → 12 KDP trim sizes + epub
- `POST /api/documents/{id}/export?format=pdf&trim={key}` → application/pdf
- `POST /api/documents/{id}/export?format=epub` → application/epub+zip
- `GET /api/ai/tools` → 5 editorial tools (public)
- `POST /api/documents/{id}/ai` `{tool, content?}` → Claude Sonnet 4.5 result
- `POST /api/documents/{id}/comments` + `/versions`
- `POST /api/integrations/{kdp|lulu}` (preparation-only, not real API hooks)

## Backlog (P1 / P2)
- P0: Connect the saved Lulu credentials to real cost calculation, file validation, print-job submission, status polling, and signed webhooks.
- P1: Refactor `server.py` (now ~2200 lines) into routers/ (auth, documents, billing, audio, admin)
- P1: Refactor EditorPage.js into smaller components (still ~2500 lines)
- P1: Real Stripe **Connect (Express)** onboarding so super-admin can auto-pay affiliates instead of manual mark-paid — requires owner's live Stripe account.
- P1: Stripe **Subscriptions** (recurring price) instead of one-time monthly payments, so renewals are auto-charged.
- P1: Rate-limit `/billing/checkout` to ~5/min per user.
- P1: Track-changes backend (diff/redline persistence)
- P2: `commissions_dlq` collection so a Mongo blip during webhook can't lose a commission row.
- P2: Webhook payload caching — reuse `event.session_id` data to avoid an extra `get_checkout_status` round-trip.
- P2: Background-queue the per-chapter audiobook export for books >5 chapters (currently sequential within the request).
- P2: Apply selected style template to PDF/ePub output (currently uses serif default)
- P2: Extend Format Preview text mapping to cover all 12 KDP trim keys
- P2: Add `DialogDescription` to dialogs to silence a11y warnings

## Test Credentials
No privileged password is stored in source control. Automated tests register and remove disposable `TEST_*` users; owner recovery uses the emailed reset flow.
