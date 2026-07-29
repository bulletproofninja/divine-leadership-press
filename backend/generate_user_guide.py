"""
Generate the Divine Leadership Press user guide PDF.

Run: `python -m generate_user_guide` from /app/backend. Outputs to
/app/frontend/public/dlp-user-guide.pdf so it's served at
{origin}/dlp-user-guide.pdf.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether, HRFlowable,
)

# DLP brand palette
NAVY = HexColor("#1a2a4a")
NAVY_LIGHT = HexColor("#2f4a7a")
CREAM = HexColor("#f5efe0")
CREAM_DEEP = HexColor("#ebe1c9")
INK = HexColor("#0f1a30")
GOLD = HexColor("#a68a3d")
MUTED = HexColor("#5a6478")

OUTPUT = Path("/app/frontend/public/dlp-user-guide.pdf")

styles = getSampleStyleSheet()
STYLE_H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontName="Times-Bold",
    fontSize=26, leading=32, textColor=NAVY, spaceAfter=8, spaceBefore=0,
)
STYLE_H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontName="Times-Bold",
    fontSize=17, leading=22, textColor=NAVY, spaceBefore=18, spaceAfter=6,
)
STYLE_H3 = ParagraphStyle(
    "H3", parent=styles["Heading3"], fontName="Times-Bold",
    fontSize=12.5, leading=16, textColor=NAVY_LIGHT, spaceBefore=10, spaceAfter=2,
)
STYLE_BODY = ParagraphStyle(
    "Body", parent=styles["BodyText"], fontName="Times-Roman",
    fontSize=10.5, leading=15, textColor=INK, alignment=TA_JUSTIFY,
    spaceAfter=6,
)
STYLE_BULLET = ParagraphStyle(
    "Bullet", parent=STYLE_BODY, leftIndent=18, bulletIndent=6,
    spaceAfter=3, alignment=TA_LEFT,
)
STYLE_LABEL = ParagraphStyle(
    "Label", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=8, textColor=GOLD, alignment=TA_CENTER,
    spaceAfter=4,
)
STYLE_META = ParagraphStyle(
    "Meta", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.5, textColor=MUTED, alignment=TA_CENTER,
)
STYLE_QUOTE = ParagraphStyle(
    "Quote", parent=STYLE_BODY, fontName="Times-Italic",
    leftIndent=18, rightIndent=18, textColor=NAVY_LIGHT,
    spaceBefore=6, spaceAfter=8,
)
STYLE_COVER_TITLE = ParagraphStyle(
    "CoverTitle", parent=STYLE_H1, fontName="Times-Bold",
    fontSize=36, leading=42, alignment=TA_CENTER, textColor=NAVY,
)
STYLE_COVER_SUB = ParagraphStyle(
    "CoverSub", parent=STYLE_BODY, fontName="Times-Italic",
    fontSize=14, leading=20, alignment=TA_CENTER, textColor=NAVY_LIGHT,
    spaceBefore=10, spaceAfter=20,
)


def bullet(text: str) -> Paragraph:
    return Paragraph(text, STYLE_BULLET, bulletText="•")


def page_bg_and_frame(canvas, doc):
    """Draw cream background + running header/footer on every page."""
    canvas.saveState()
    # Cream page
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    # Top ornamental rule
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(2)
    canvas.line(0.75 * inch, doc.pagesize[1] - 0.55 * inch,
                doc.pagesize[0] - 0.75 * inch, doc.pagesize[1] - 0.55 * inch)
    canvas.setLineWidth(0.4)
    canvas.line(0.75 * inch, doc.pagesize[1] - 0.60 * inch,
                doc.pagesize[0] - 0.75 * inch, doc.pagesize[1] - 0.60 * inch)
    # Running header
    canvas.setFont("Times-Italic", 9)
    canvas.setFillColor(NAVY)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, doc.pagesize[1] - 0.42 * inch,
        "DIVINE LEADERSHIP PRESS — Publisher's User Guide",
    )
    # Bottom ornamental rule + page number
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.4)
    canvas.line(0.75 * inch, 0.60 * inch,
                doc.pagesize[0] - 0.75 * inch, 0.60 * inch)
    canvas.setLineWidth(2)
    canvas.line(0.75 * inch, 0.55 * inch,
                doc.pagesize[0] - 0.75 * inch, 0.55 * inch)
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, 0.38 * inch, f"— {doc.page} —",
    )
    canvas.restoreState()


def cover_page(canvas, doc):
    """Full-bleed navy cover with cream typography."""
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    # Cream ornamental rules
    canvas.setStrokeColor(CREAM)
    canvas.setLineWidth(2)
    canvas.line(1.0 * inch, doc.pagesize[1] - 1.4 * inch,
                doc.pagesize[0] - 1.0 * inch, doc.pagesize[1] - 1.4 * inch)
    canvas.setLineWidth(0.4)
    canvas.line(1.0 * inch, doc.pagesize[1] - 1.5 * inch,
                doc.pagesize[0] - 1.0 * inch, doc.pagesize[1] - 1.5 * inch)
    # Small label
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.setFillColor(GOLD)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, doc.pagesize[1] - 1.9 * inch,
        "EST. 1925    ·    A CENTURY OF LETTERPRESS CRAFT",
    )
    # Title
    canvas.setFont("Times-Bold", 42)
    canvas.setFillColor(CREAM)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, doc.pagesize[1] - 3.2 * inch, "Divine",
    )
    canvas.drawCentredString(
        doc.pagesize[0] / 2, doc.pagesize[1] - 3.9 * inch, "Leadership Press",
    )
    # Subtitle
    canvas.setFont("Times-Italic", 16)
    canvas.setFillColor(CREAM_DEEP)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, doc.pagesize[1] - 4.7 * inch,
        "The Publisher's User Guide",
    )
    canvas.setFont("Times-Roman", 12)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, doc.pagesize[1] - 5.05 * inch,
        "Manuscript to marketplace — how the modern press works.",
    )
    # Bottom footer on cover
    canvas.setStrokeColor(CREAM)
    canvas.setLineWidth(0.4)
    canvas.line(1.0 * inch, 1.5 * inch,
                doc.pagesize[0] - 1.0 * inch, 1.5 * inch)
    canvas.setLineWidth(2)
    canvas.line(1.0 * inch, 1.4 * inch,
                doc.pagesize[0] - 1.0 * inch, 1.4 * inch)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.setFillColor(GOLD)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, 1.05 * inch,
        f"VOL. I     ·     {datetime.now(timezone.utc).strftime('%B %Y').upper()}",
    )
    canvas.setFont("Times-Italic", 10)
    canvas.setFillColor(CREAM_DEEP)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, 0.75 * inch,
        "For authors, imprints, and the small houses that raise them.",
    )
    canvas.restoreState()


# ---- FLOWABLES ------------------------------------------------------------

def cover_section() -> list:
    """Cover is drawn on the canvas — we just eat the page with a spacer."""
    return [Spacer(1, 8.5 * inch), PageBreak()]


def intro_section() -> list:
    s = []
    s.append(Paragraph("A Word from the Press", STYLE_H1))
    s.append(HRFlowable(width="15%", thickness=1.4, color=NAVY, spaceBefore=2, spaceAfter=10))
    s.append(Paragraph(
        "For a hundred years, our house has done one thing well: put beautiful, "
        "well-edited books into the hands of readers who deserve them. What used "
        "to take a printing floor now takes a browser tab — but the craft has not "
        "changed. This guide walks you through every desk of the modern press: "
        "the editor's desk, the audio booth, the pressroom, and the counting "
        "house. Read it once and you will know how to move a manuscript from "
        "first sentence to KDP-ready file — with an audiobook, an affiliate "
        "program, and a paid subscription business attached.",
        STYLE_BODY,
    ))
    s.append(Paragraph(
        "&#8220;An author who understands their tools writes twice as much, "
        "twice as well.&#8221;",
        STYLE_QUOTE,
    ))
    return s


def use_case_section() -> list:
    s = [Paragraph("The Use Case", STYLE_H1),
         HRFlowable(width="15%", thickness=1.4, color=NAVY, spaceBefore=2, spaceAfter=10)]
    s.append(Paragraph(
        "Divine Leadership Press is a full-stack writing and publishing "
        "workroom for people who intend to publish a book — not one day, but "
        "this year. It replaces the ragged chain of Word, Grammarly, Vellum, "
        "Descript, Canva, KDP, and PayPal with a single studio.",
        STYLE_BODY,
    ))

    s.append(Paragraph("What the studio does", STYLE_H2))
    for line in [
        "<b>Manuscript intake.</b> Upload a .docx, .txt, or Google-Docs export; "
        "the file is parsed into a clean HTML manuscript you can edit in the browser.",
        "<b>Editorial polish.</b> Claude Sonnet 4.5 tightens, clarifies, "
        "and writes back-cover blurbs on demand. A separate copy-edit pass "
        "checks the whole manuscript against Chicago / AP / DLP house style.",
        "<b>Formatting for print.</b> One-click PDF export at every KDP trim "
        "size (5×8 through 8.5×11), plus a validated ePub for retailers.",
        "<b>Audiobook production.</b> Full-book narration through OpenAI HD "
        "voices, or professional narration through an ElevenLabs key — "
        "including voice cloning of the author's own voice.",
        "<b>Per-chapter audiobook export.</b> Ships a ZIP of one MP3 per "
        "chapter for retailers that require chapter files (KDP Audible, "
        "Audiobooks.com).",
        "<b>Dictation &amp; voice memos.</b> Dictate paragraphs directly into "
        "the manuscript via OpenAI Whisper; leave audio notes on any paragraph.",
        "<b>Cover art intake.</b> Upload a JPG/PNG/WebP cover, or hand us an "
        "image and we'll wrap it as a print-ready PDF for KDP.",
        "<b>Writing agent.</b> A Claude-powered co-author lives in a sidebar. "
        "It knows the manuscript, matches the author's voice, and rewrites "
        "any selection with <b>Cmd-K</b>.",
        "<b>Affiliate program.</b> Every author receives a referral code; "
        "signup and MRR commissions accrue automatically and pay out through "
        "Stripe Connect.",
        "<b>Subscription business.</b> Two plans (Author Pro $19/mo, Estate "
        "$49/mo) built on live Stripe subscriptions with a self-service "
        "customer portal.",
    ]:
        s.append(bullet(line))

    s.append(Paragraph("Who it is for", STYLE_H2))
    for line in [
        "<b>Indie authors</b> shipping their first or fifth book — one workflow, "
        "no context-switching between six tools.",
        "<b>Ghostwriters and co-authors</b> collaborating on client manuscripts.",
        "<b>Small imprints and church / leadership presses</b> publishing "
        "several books a year without a printing floor.",
        "<b>Course creators and executives</b> turning existing material into "
        "leadable books — chapters dictated on a commute, polished in an evening.",
        "<b>Speakers and podcasters</b> repurposing spoken material into "
        "audiobooks and printed volumes.",
    ]:
        s.append(bullet(line))
    return s


def market_section() -> list:
    s = [Paragraph("Where It Fits in the Market", STYLE_H1),
         HRFlowable(width="15%", thickness=1.4, color=NAVY, spaceBefore=2, spaceAfter=10)]
    s.append(Paragraph(
        "The self-publishing market ships more than 2 million titles a year "
        "and grows every quarter. The bottleneck is not audience or "
        "distribution — Amazon KDP, Lulu, Audible and Draft2Digital already "
        "put a finished book on 40+ retailers. The bottleneck is the middle: "
        "the messy, tool-fragmented pipeline between a rough manuscript and a "
        "retailer-ready file.",
        STYLE_BODY,
    ))

    s.append(Paragraph("Positioning", STYLE_H2))
    data = [
        ["Tool", "Solves", "DLP replaces / augments"],
        ["Word / Google Docs", "Draft", "Rich editor + AI polish + voice memos"],
        ["Grammarly / ProWritingAid", "Line edit", "Full copy-edit pass against Chicago/AP/DLP"],
        ["Vellum / Atticus", "Print format", "One-click PDF at 12 KDP trim sizes + ePub"],
        ["Descript / ElevenLabs", "Narration", "OpenAI HD + BYO-key ElevenLabs, per-chapter export"],
        ["Canva / Photoshop", "Cover art", "Cover upload + auto image-to-PDF for KDP"],
        ["Amazon Associates", "Referral", "Native 30% signup + 10% MRR, auto-payout"],
        ["Stripe direct", "Payments", "Turnkey subscription + Connect payouts"],
    ]
    tbl = Table(data, colWidths=[1.6*inch, 1.9*inch, 3.0*inch])
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Times-Roman", 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), CREAM),
        ("BACKGROUND", (0, 1), (-1, -1), CREAM_DEEP),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CREAM, CREAM_DEEP]),
        ("GRID", (0, 0), (-1, -1), 0.4, NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    s.append(tbl)

    s.append(Paragraph("Go-to-market plays", STYLE_H2))
    for line in [
        "<b>Speaker and coach launch bundle.</b> Sell the book, the audiobook, "
        "and the printed edition as a $49–99 bundle at events; DLP produces all "
        "three from one manuscript.",
        "<b>Ghostwriter agency stack.</b> Ghostwriters manage 8–15 client "
        "manuscripts side by side; the AI polish and voice-match agent halve "
        "editing rounds.",
        "<b>Church, leadership, and legacy imprint.</b> A pastor or founder's "
        "sermon library becomes a five-book collection in one quarter — "
        "chapters dictated, agents matched to the founder's voice.",
        "<b>Affiliate flywheel.</b> Every published author is a natural "
        "advocate for their tool. 30% signup + 10% MRR sends real cash to "
        "referring authors — the marketing budget lives inside the product.",
    ]:
        s.append(bullet(line))
    return s


def features_section() -> list:
    s = [Paragraph("What Ships Today", STYLE_H1),
         HRFlowable(width="15%", thickness=1.4, color=NAVY, spaceBefore=2, spaceAfter=10)]
    modules = [
        ("Manuscript studio",
         "Rich editor with H1/H2 chapter structure, style templates, track-changes toggle, "
         "word/character counter, and quick-tip sidebar. Every save is versioned."),
        ("File intake",
         "Drag-and-drop .docx / .txt upload. Documents parsed into clean HTML with "
         "chapter boundaries preserved."),
        ("AI editorial polish (Claude Sonnet 4.5)",
         "Tighten prose, clarify muddy passages, generate blurbs. Full copy-edit "
         "pass against Chicago Manual of Style, AP, or DLP house style."),
        ("Writing agent",
         "Persistent per-document chat companion plus Cmd-K inline command. 7 voice "
         "presets including 'Match my voice' — samples existing chapters."),
        ("Export pipeline",
         "PDF at 12 KDP trim sizes (5×8, 5.06×7.81, 5.25×8, 5.5×8.5, 6×9, "
         "6.14×9.21, 6.69×9.61, 7×10, 7.44×9.69, 7.5×9.25, 8×10, 8.5×11) + validated ePub."),
        ("Audio studio",
         "OpenAI HD narration for full audiobooks; ElevenLabs premium narration "
         "and voice cloning with your own key; per-chapter ZIP export."),
        ("Dictation &amp; voice memos",
         "OpenAI Whisper dictation, continuous mode for long-form, and paragraph-anchored voice memos."),
        ("Cover art &amp; KDP setup",
         "Cover upload, image-to-PDF conversion for KDP print covers, "
         "author/subtitle/description metadata, publication pipeline badges."),
        ("Referral &amp; affiliate program",
         "Auto-generated referral codes, live leaderboard, badge tiers, and "
         "commission accrual (30% signup + 10% MRR within 60 days)."),
        ("Live Stripe subscriptions",
         "Author Pro $19/mo and Estate $49/mo billed monthly through Stripe "
         "Checkout. Self-serve customer portal for cancellations."),
        ("Stripe Connect payouts",
         "Affiliates onboard through Stripe Express; the owner's dashboard "
         "batch-transfers commissions with one click."),
        ("Owner dashboard",
         "Super-admin controls at /admin/affiliate (program settings) and "
         "/admin/commissions (payout ledger + auto-pay via Stripe)."),
    ]
    for title, body in modules:
        s.append(Paragraph(title, STYLE_H3))
        s.append(Paragraph(body, STYLE_BODY))
    return s


def faq_section() -> list:
    s = [Paragraph("Frequently Asked Questions", STYLE_H1),
         HRFlowable(width="15%", thickness=1.4, color=NAVY, spaceBefore=2, spaceAfter=10)]
    faqs = [
        ("Is the AI writing my book for me?",
         "No. The agent is a co-author, not a ghostwriter. It helps you brainstorm, "
         "rewrite a paragraph in your voice, or find the strongest sentence you "
         "already wrote. You own every word; the AI never publishes anything on your behalf."),
        ("Which retailers can I sell on?",
         "Any retailer that accepts a PDF or ePub — that is essentially all of them. "
         "Verified pipelines exist for Amazon KDP (paperback + Kindle), Lulu, "
         "Draft2Digital, IngramSpark, and Audible / ACX for the audiobook."),
        ("Do you take a cut of my book sales?",
         "Never. You keep 100% of royalties from KDP, Lulu, etc. DLP is a monthly "
         "subscription — the only money you send us is the plan fee."),
        ("What are the plans and what's included?",
         "<b>Author Pro — $19/mo.</b> Unlimited manuscripts, unlimited writing "
         "agent, PDF/ePub at every trim size, OpenAI audiobook, dictation, "
         "voice memos, affiliate program. "
         "<b>Estate — $49/mo.</b> Adds priority Claude/OpenAI quotas, bulk "
         "per-chapter audiobook export, higher payout priority, and early "
         "access to new features."),
        ("Can I try the writing agent for free?",
         "Yes. Free accounts get five agent messages per day (chat + Cmd-K "
         "combined). Unused messages don't roll over; the quota resets at "
         "midnight UTC. Author Pro removes the cap."),
        ("How do the affiliate payouts work?",
         "Every author has a referral code. When someone signs up through your "
         "link and subscribes, you earn 30% of their first payment and 10% of "
         "every renewal for 60 days. Payouts run through Stripe Connect Express "
         "directly to your bank."),
        ("Do I need my own ElevenLabs / OpenAI account?",
         "No. OpenAI HD narration, Whisper dictation, and Claude editing all "
         "run on the DLP-managed universal key. ElevenLabs is optional — bring "
         "your own key if you want their premium voices or to clone your own."),
        ("Is my manuscript private?",
         "Yes. Documents are visible only to the author's account. Nothing is "
         "shared, sold, or used to train models. The AI features send passages "
         "to the model provider (Anthropic / OpenAI) for that single call and "
         "no retention beyond that."),
        ("What happens to my documents if I cancel?",
         "Your manuscripts remain in the account; you keep read-only access. "
         "Re-subscribing at any time restores full editing, export, and audio "
         "generation."),
        ("Does DLP support voice cloning?",
         "Yes — through ElevenLabs. Under Audio Studio → ElevenLabs, connect "
         "your key and upload a 60-second sample. The cloned voice becomes "
         "available to any of your manuscripts."),
        ("Can I export a single chapter as an audiobook?",
         "Yes. On any document, open Audio Studio → OpenAI, click <b>Detect "
         "chapters</b> to preview the H1/H2 split, then <b>Export ZIP</b>. "
         "The archive contains one MP3 per chapter plus a tracklist."),
        ("Which trim size should I choose for KDP?",
         "For most trade non-fiction and memoir, <b>6×9</b> is the standard. "
         "Fiction and business books commonly use <b>5.5×8.5</b>. Poetry looks "
         "best in <b>5×8</b>. The full 12-size list is available in the export "
         "dialog with KDP-recommended defaults."),
    ]
    for q, a in faqs:
        s.append(Paragraph(f"Q. {q}", STYLE_H3))
        s.append(Paragraph(f"A. {a}", STYLE_BODY))
    return s


def troubleshooting_section() -> list:
    s = [Paragraph("Troubleshooting Guide", STYLE_H1),
         HRFlowable(width="15%", thickness=1.4, color=NAVY, spaceBefore=2, spaceAfter=10)]
    s.append(Paragraph(
        "Symptoms first, remedies second. If none of the fixes resolve the "
        "issue, email support with the URL you were on, the exact error text, "
        "and a screenshot; we typically reply within one business day.",
        STYLE_BODY,
    ))

    problems = [
        ("The writing agent won't respond and I see &#8220;out of free messages&#8221;.",
         "Free accounts are limited to five agent messages per UTC day. The quota "
         "resets at midnight UTC. To remove the limit, subscribe to Author Pro at "
         "/billing. If you are already subscribed and still see the lock, sign out "
         "and back in — the local cache may be stale."),
        ("My subscription was charged but /billing still says I'm not subscribed.",
         "Refresh the page. If the status stays wrong for more than a minute, "
         "open the browser console and check whether /api/billing/me returns "
         "the correct plan. If it returns active=false with your payment recorded "
         "in Stripe, the webhook receipt is stalled — email support with the "
         "Stripe payment ID (pi_...)."),
        ("My .docx upload failed with &#8220;could not parse file&#8221;.",
         "Ensure the file is a genuine Word .docx, not a renamed .doc or .pages. "
         "Very large images inside the manuscript can also cause failures — "
         "remove images before uploading and re-add them in the browser editor."),
        ("PDF export took over a minute and then timed out.",
         "Extremely long manuscripts (300+ pages with many images) can exceed "
         "the export timeout. Export one section at a time, or split the "
         "manuscript into two documents. Contact support if you consistently "
         "hit this — we can raise the timeout on your account."),
        ("The audiobook generation errored with &#8220;manuscript is too long&#8221;.",
         "The full-book audiobook endpoint caps at about 17,000 words per run. "
         "For longer books, use the per-chapter export instead — it splits at "
         "H1/H2 headings and processes each chapter individually."),
        ("Per-chapter audiobook says &#8220;only one chapter detected&#8221;.",
         "The splitter uses H1 or H2 headings as chapter boundaries. Open the "
         "manuscript, highlight each chapter title, and apply Heading 1 from "
         "the formatting toolbar. Save, then try again."),
        ("Dictation button opens the mic but nothing gets transcribed.",
         "Grant the browser microphone permission (padlock icon in the address "
         "bar). Also make sure your microphone is the default input device. "
         "If continuous dictation drops out, disable browser extensions that "
         "intercept audio (Loom, Otter, etc.)."),
        ("Cover upload succeeded but the thumbnail doesn't appear.",
         "Cover images are cached for five minutes. Refresh the page. If it "
         "still doesn't appear, ensure the image is under 10 MB and in JPG, "
         "PNG, or WebP format."),
        ("&#8220;Payout account not ready&#8221; when I try to auto-pay affiliates.",
         "The affiliate must complete Stripe Express onboarding first — they'll "
         "see the &#8220;Connect with Stripe&#8221; button on their /help page. "
         "Also confirm your platform's Stripe Connect is enabled at "
         "dashboard.stripe.com/connect."),
        ("&#8220;Stripe Connect is not yet enabled&#8221; when an affiliate clicks Connect.",
         "The platform account owner must enable Connect once at "
         "dashboard.stripe.com/connect and complete the platform profile. "
         "Once done, affiliate onboarding works with no further code changes."),
        ("Renewal charge succeeded but the subscription didn't extend.",
         "Verify the webhook endpoint (dashboard.stripe.com/webhooks) is "
         "receiving invoice.paid events. If Stripe shows recent 4xx delivery "
         "failures for that endpoint, re-copy the STRIPE_WEBHOOK_SECRET into "
         "backend/.env and restart the backend."),
        ("The editor is stuck on &#8220;Saving…&#8221;.",
         "Check the browser console for a red 401 or 502 error. A 401 means "
         "your session expired — sign out and back in. A 502 means the "
         "backend is momentarily overloaded; wait ten seconds and click "
         "Save again."),
        ("I can't reach /admin/affiliate or /admin/commissions.",
         "Both pages require super-admin privileges. Only the seeded owner "
         "account has them. If you need a second admin, ask the owner to "
         "run the seed script with your email."),
    ]
    for symptom, fix in problems:
        s.append(Paragraph(f"Symptom &nbsp;· &nbsp;{symptom}", STYLE_H3))
        s.append(Paragraph(f"<b>Fix.</b> {fix}", STYLE_BODY))
    return s


def closing_section() -> list:
    s = [PageBreak(),
         Paragraph("Getting Help", STYLE_H1),
         HRFlowable(width="15%", thickness=1.4, color=NAVY, spaceBefore=2, spaceAfter=10)]
    s.append(Paragraph(
        "For questions not covered in this guide, visit the in-app <b>Help</b> "
        "page from any screen, or click the referral / affiliate section for "
        "your unique code and leaderboard standing.",
        STYLE_BODY,
    ))
    s.append(Spacer(1, 12))
    s.append(Paragraph(
        "&#8220;The press was never the paper. The press was the promise you "
        "made to the reader.&#8221;",
        STYLE_QUOTE,
    ))
    s.append(Spacer(1, 24))
    s.append(HRFlowable(width="30%", thickness=1.4, color=NAVY, spaceBefore=2, spaceAfter=10, hAlign="CENTER"))
    s.append(Paragraph(
        f"DIVINE LEADERSHIP PRESS · VOL. I · {datetime.now(timezone.utc).strftime('%B %Y').upper()}",
        STYLE_LABEL,
    ))
    s.append(Paragraph("A century-old imprint, freshly re-set in code.", STYLE_META))
    return s


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=LETTER,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        title="Divine Leadership Press — Publisher's User Guide",
        author="Divine Leadership Press",
        subject="Product use cases, market positioning, FAQ, and troubleshooting.",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="main",
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover_page),
        PageTemplate(id="body", frames=[frame], onPage=page_bg_and_frame),
    ])

    story: list = []
    story += cover_section()
    # Manually switch to body template
    from reportlab.platypus.doctemplate import NextPageTemplate
    story = [NextPageTemplate("body")] + story
    story += intro_section()
    story += use_case_section()
    story.append(PageBreak())
    story += market_section()
    story.append(PageBreak())
    story += features_section()
    story.append(PageBreak())
    story += faq_section()
    story.append(PageBreak())
    story += troubleshooting_section()
    story += closing_section()

    doc.build(story)
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"OK: wrote {OUTPUT}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    build()
