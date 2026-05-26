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
- P1: Refactor EditorPage.js into smaller components (still ~540 lines)
- P1: Refactor server.py into routers/ (auth, documents, exports)
- P1: Track-changes backend (diff/redline persistence)
- P2: Cover image upload for books
- P2: Apply selected style template to PDF/ePub output (currently uses serif default)
- P2: Extend Format Preview text mapping to cover all 12 KDP trim keys
- P2: Replace `jwt.JWTError` with `jwt.PyJWTError` (PyJWT 2.x hardening)
- P2: Add `DialogDescription` to dialogs to silence a11y warnings

## Test Credentials
None pre-seeded. Tests register fresh users on the fly.
