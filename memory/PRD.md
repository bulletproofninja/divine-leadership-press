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
  - Storage: file on disk under `/app/backend/uploads/memos/{user_id}/{document_id}/`, metadata in `document.memos` array
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
│   ├── exporters.py       # KDP_TRIM_SIZES, docx_to_html, generate_pdf, generate_epub
│   ├── ai_editor.py       # Claude Sonnet 4.5 editorial tools (5 endpoints)
│   ├── tests/test_upload_export.py
│   ├── tests/test_ai_editorial.py
│   └── requirements.txt   # + reportlab, beautifulsoup4, ebooklib, python-docx, emergentintegrations
├── frontend/src/pages/
│   ├── LandingPage.js
│   ├── Dashboard.js       # upload accepts .docx/.txt/.pages
│   └── EditorPage.js      # blob-download export, trim-size selector
```

## API Endpoints
- `POST /api/auth/register | /login | GET /api/auth/me`
- `GET|POST|PUT|DELETE /api/documents[/{id}]`
- `POST /api/documents/upload` (.docx, .txt; .pages → 400 with guidance)
- `GET /api/export/formats` → 12 KDP trim sizes + epub
- `POST /api/documents/{id}/export?format=pdf&trim={key}` → application/pdf
- `POST /api/documents/{id}/export?format=epub` → application/epub+zip
- `GET /api/ai/tools` → 5 editorial tools (public)
- `POST /api/documents/{id}/ai` `{tool, content?}` → Claude Sonnet 4.5 result
- `POST /api/documents/{id}/comments` + `/versions`
- `POST /api/integrations/{kdp|lulu}` (preparation-only, not real API hooks)

## Backlog (P1 / P2)
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
- P2: Replace `jwt.JWTError` with `jwt.PyJWTError` (PyJWT 2.x hardening)
- P2: Add `DialogDescription` to dialogs to silence a11y warnings

## Test Credentials
None pre-seeded. Tests register fresh users on the fly.
