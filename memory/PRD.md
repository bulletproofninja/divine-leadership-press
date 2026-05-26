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
- [x] Backend pytest suite at `/app/backend/tests/test_upload_export.py` (14/14 passing)

## Architecture
```
/app/
├── backend/
│   ├── server.py          # FastAPI app: auth, documents, upload, export, integrations
│   ├── exporters.py       # KDP_TRIM_SIZES, docx_to_html, generate_pdf, generate_epub
│   ├── tests/test_upload_export.py
│   └── requirements.txt   # + reportlab, beautifulsoup4, ebooklib, python-docx
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
