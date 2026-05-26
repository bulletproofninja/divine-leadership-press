"""
Divine Leadership Press — Export & Import utilities.
Handles PDF generation for all standard KDP trim sizes, ePub generation,
and parsing uploaded .docx documents into rich HTML for the editor.
"""
import io
import re
import uuid
from html import escape
from typing import Dict, Tuple, List, Optional

from bs4 import BeautifulSoup, NavigableString
from docx import Document as DocxDocument
from ebooklib import epub
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.units import inch as INCH
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage
)
from reportlab.platypus.tableofcontents import TableOfContents


# All standard Amazon KDP trim sizes (width x height in inches)
KDP_TRIM_SIZES: Dict[str, Tuple[float, float]] = {
    "5x8":        (5.00, 8.00),
    "5.06x7.81":  (5.06, 7.81),
    "5.25x8":     (5.25, 8.00),
    "5.5x8.5":    (5.50, 8.50),
    "6x9":        (6.00, 9.00),
    "6.14x9.21":  (6.14, 9.21),
    "6.69x9.61":  (6.69, 9.61),
    "7x10":       (7.00, 10.00),
    "7.44x9.69":  (7.44, 9.69),
    "7.5x9.25":   (7.50, 9.25),
    "8x10":       (8.00, 10.00),
    "8.5x11":     (8.50, 11.00),  # Magazine / Letter
}


def get_trim_size(format_key: str) -> Tuple[float, float]:
    """Returns (width_pts, height_pts) for a trim size key. Defaults to 6x9."""
    w_in, h_in = KDP_TRIM_SIZES.get(format_key, KDP_TRIM_SIZES["6x9"])
    return (w_in * INCH, h_in * INCH)


# ---------------------------------------------------------------------------
# DOCX import → HTML (preserves bold/italic/underline/headings/lists)
# ---------------------------------------------------------------------------
def docx_to_html(file_bytes: bytes) -> str:
    """Parse a .docx file into HTML suitable for ReactQuill."""
    doc = DocxDocument(io.BytesIO(file_bytes))
    html_parts: List[str] = []
    list_open: Optional[str] = None  # 'ul' or 'ol'

    def close_list():
        nonlocal list_open
        if list_open:
            html_parts.append(f"</{list_open}>")
            list_open = None

    for para in doc.paragraphs:
        text_runs: List[str] = []
        for run in para.runs:
            t = escape(run.text or "")
            if not t:
                continue
            if run.bold:
                t = f"<strong>{t}</strong>"
            if run.italic:
                t = f"<em>{t}</em>"
            if run.underline:
                t = f"<u>{t}</u>"
            text_runs.append(t)
        inner = "".join(text_runs) or "<br>"

        style_name = (para.style.name or "").lower() if para.style else ""

        # Headings
        m = re.match(r"heading (\d)", style_name)
        if m:
            close_list()
            level = min(int(m.group(1)), 6)
            html_parts.append(f"<h{level}>{inner}</h{level}>")
            continue

        # Lists (docx represents bullet/number lists via style names)
        if "list bullet" in style_name or "list paragraph" in style_name and para.text.strip().startswith(("•", "-", "*")):
            if list_open != "ul":
                close_list()
                html_parts.append("<ul>")
                list_open = "ul"
            html_parts.append(f"<li>{inner}</li>")
            continue
        if "list number" in style_name:
            if list_open != "ol":
                close_list()
                html_parts.append("<ol>")
                list_open = "ol"
            html_parts.append(f"<li>{inner}</li>")
            continue

        close_list()

        # Alignment
        align = ""
        if para.alignment is not None:
            align_map = {1: "center", 2: "right", 3: "justify"}
            css = align_map.get(int(para.alignment), "")
            if css:
                align = f' style="text-align:{css};"'

        if not para.text.strip():
            html_parts.append("<p><br></p>")
        else:
            html_parts.append(f"<p{align}>{inner}</p>")

    close_list()
    return "".join(html_parts)


# ---------------------------------------------------------------------------
# HTML → PDF (KDP trim sizes)
# ---------------------------------------------------------------------------
def _build_pdf_styles(trim_w: float, trim_h: float) -> Dict[str, ParagraphStyle]:
    """Build a Garamond-style serif stylesheet scaled to trim size."""
    base_font = "Times-Roman"  # built-in serif (no external dep)
    bold_font = "Times-Bold"
    italic_font = "Times-Italic"

    # Body font scales modestly for larger trims
    body_size = 11 if trim_w < 6 * INCH else 11.5
    leading = body_size * 1.45

    styles: Dict[str, ParagraphStyle] = {
        "body": ParagraphStyle(
            "body", fontName=base_font, fontSize=body_size, leading=leading,
            alignment=TA_JUSTIFY, firstLineIndent=0.25 * INCH, spaceAfter=0,
            textColor="#1a1a1a",
        ),
        "h1": ParagraphStyle(
            "h1", fontName=bold_font, fontSize=22, leading=28,
            alignment=TA_CENTER, spaceBefore=24, spaceAfter=18, textColor="#0b1d3a",
        ),
        "h2": ParagraphStyle(
            "h2", fontName=bold_font, fontSize=17, leading=22,
            alignment=TA_LEFT, spaceBefore=18, spaceAfter=10, textColor="#0b1d3a",
        ),
        "h3": ParagraphStyle(
            "h3", fontName=bold_font, fontSize=13.5, leading=18,
            alignment=TA_LEFT, spaceBefore=12, spaceAfter=6, textColor="#0b1d3a",
        ),
        "h4": ParagraphStyle(
            "h4", fontName=italic_font, fontSize=12, leading=16,
            alignment=TA_LEFT, spaceBefore=10, spaceAfter=4,
        ),
        "blockquote": ParagraphStyle(
            "blockquote", fontName=italic_font, fontSize=body_size, leading=leading,
            alignment=TA_LEFT, leftIndent=0.4 * INCH, rightIndent=0.4 * INCH,
            textColor="#444444", spaceBefore=8, spaceAfter=8,
        ),
        "li": ParagraphStyle(
            "li", fontName=base_font, fontSize=body_size, leading=leading,
            alignment=TA_LEFT, leftIndent=0.3 * INCH, bulletIndent=0.1 * INCH,
        ),
        "title": ParagraphStyle(
            "title", fontName=bold_font, fontSize=28, leading=34,
            alignment=TA_CENTER, spaceBefore=trim_h * 0.25, spaceAfter=18,
            textColor="#0b1d3a",
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName=italic_font, fontSize=14, leading=20,
            alignment=TA_CENTER, spaceAfter=8, textColor="#555555",
        ),
    }
    return styles


def _html_to_rl_flowables(html: str, styles: Dict[str, ParagraphStyle]) -> List:
    """Convert sanitised HTML into a list of ReportLab flowables."""
    soup = BeautifulSoup(html or "", "html.parser")
    flowables: List = []

    # Top-level handling: walk direct children of root
    for el in soup.children:
        if isinstance(el, NavigableString):
            txt = str(el).strip()
            if txt:
                flowables.append(Paragraph(escape(txt), styles["body"]))
            continue

        name = el.name.lower() if el.name else ""
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(name[1])
            style_key = f"h{min(level, 4)}"
            inner = _inline_html(el)
            if inner.strip():
                flowables.append(Paragraph(inner, styles[style_key]))
        elif name == "p":
            inner = _inline_html(el)
            if not inner.strip() or inner.strip() == "<br/>":
                flowables.append(Spacer(1, 8))
            else:
                # Honour text-align via style attr
                align = (el.get("style") or "").lower()
                style = styles["body"]
                if "text-align:center" in align:
                    style = ParagraphStyle("c", parent=style, alignment=TA_CENTER, firstLineIndent=0)
                elif "text-align:right" in align:
                    style = ParagraphStyle("r", parent=style, alignment=TA_RIGHT, firstLineIndent=0)
                elif "text-align:left" in align:
                    style = ParagraphStyle("l", parent=style, alignment=TA_LEFT, firstLineIndent=0)
                flowables.append(Paragraph(inner, style))
        elif name == "blockquote":
            inner = _inline_html(el)
            if inner.strip():
                flowables.append(Paragraph(inner, styles["blockquote"]))
        elif name in ("ul", "ol"):
            for li in el.find_all("li", recursive=False):
                inner = _inline_html(li)
                bullet = "•" if name == "ul" else f"{el.find_all('li', recursive=False).index(li) + 1}."
                flowables.append(Paragraph(f"{bullet} &nbsp;{inner}", styles["li"]))
        elif name == "br":
            flowables.append(Spacer(1, 8))
        else:
            inner = _inline_html(el)
            if inner.strip():
                flowables.append(Paragraph(inner, styles["body"]))

    return flowables


def _inline_html(node) -> str:
    """Render inline HTML (b/i/u/strong/em/a/br/span) safely for ReportLab paragraphs."""
    parts: List[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(escape(str(child)))
            continue
        tag = child.name.lower()
        inner = _inline_html(child)
        if tag in ("b", "strong"):
            parts.append(f"<b>{inner}</b>")
        elif tag in ("i", "em"):
            parts.append(f"<i>{inner}</i>")
        elif tag == "u":
            parts.append(f"<u>{inner}</u>")
        elif tag == "br":
            parts.append("<br/>")
        elif tag == "a":
            href = child.get("href", "")
            parts.append(f'<link href="{escape(href)}" color="#0b1d3a">{inner}</link>')
        elif tag == "span":
            parts.append(inner)
        elif tag == "code":
            parts.append(f"<font face='Courier'>{inner}</font>")
        else:
            parts.append(inner)
    return "".join(parts)


def generate_pdf(
    *,
    title: str,
    author: Optional[str],
    html_content: str,
    trim_key: str = "6x9",
    publisher: Optional[str] = None,
) -> bytes:
    """Render the document to a publishing-grade PDF at the given KDP trim size."""
    trim_w, trim_h = get_trim_size(trim_key)
    styles = _build_pdf_styles(trim_w, trim_h)

    # KDP-style mirrored margins (gutter > outer for binding)
    inner_margin = 0.75 * INCH
    outer_margin = 0.5 * INCH
    top_margin = 0.75 * INCH
    bottom_margin = 0.75 * INCH

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(trim_w, trim_h),
        leftMargin=inner_margin,
        rightMargin=outer_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=title,
        author=author or "",
    )

    story: List = []

    # Title page
    story.append(Paragraph(escape(title or "Untitled"), styles["title"]))
    if author:
        story.append(Paragraph(escape(author), styles["subtitle"]))
    if publisher:
        story.append(Spacer(1, trim_h * 0.05))
        story.append(Paragraph(escape(publisher), styles["subtitle"]))
    story.append(PageBreak())

    # Body
    story.extend(_html_to_rl_flowables(html_content or "", styles))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Times-Roman", 9)
        canvas.setFillColorRGB(0.4, 0.4, 0.4)
        page_num = doc_.page
        # Skip page number on title page
        if page_num > 1:
            canvas.drawCentredString(trim_w / 2.0, 0.4 * INCH, str(page_num - 1))
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# HTML → ePub
# ---------------------------------------------------------------------------
def generate_epub(
    *,
    title: str,
    author: Optional[str],
    html_content: str,
    language: str = "en",
    publisher: Optional[str] = None,
) -> bytes:
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title or "Untitled")
    book.set_language(language or "en")
    if author:
        book.add_author(author)
    if publisher:
        book.add_metadata("DC", "publisher", publisher)

    # Split content into chapters by h1; otherwise single chapter
    soup = BeautifulSoup(html_content or "", "html.parser")
    h1s = soup.find_all("h1")

    css = epub.EpubItem(
        uid="style_main",
        file_name="style/main.css",
        media_type="text/css",
        content=(
            "body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.6; }"
            "h1 { font-family: Georgia, serif; color: #0b1d3a; text-align: center; "
            "margin-top: 2em; }"
            "h2 { font-family: Georgia, serif; color: #0b1d3a; }"
            "p { text-indent: 1.5em; margin: 0 0 0.4em 0; text-align: justify; }"
            "p.first { text-indent: 0; }"
            "blockquote { font-style: italic; color: #444; margin: 1em 2em; }"
        ),
    )
    book.add_item(css)

    chapters = []

    def _make_chapter(idx: int, ch_title: str, ch_html: str):
        c = epub.EpubHtml(
            title=ch_title or f"Chapter {idx + 1}",
            file_name=f"chap_{idx + 1}.xhtml",
            lang=language or "en",
        )
        c.content = (
            f"<html><head><title>{escape(ch_title)}</title>"
            f"<link rel='stylesheet' type='text/css' href='style/main.css'/></head>"
            f"<body>{ch_html}</body></html>"
        )
        c.add_item(css)
        book.add_item(c)
        chapters.append(c)

    if h1s:
        # Split: each H1 starts a new chapter
        sections: List[Tuple[str, List]] = []
        current_title = title or "Introduction"
        current_nodes: List = []
        for child in list(soup.children):
            if getattr(child, "name", None) == "h1":
                if current_nodes:
                    sections.append((current_title, current_nodes))
                current_title = child.get_text(strip=True) or current_title
                current_nodes = []
            else:
                current_nodes.append(child)
        if current_nodes:
            sections.append((current_title, current_nodes))

        for idx, (ch_title, nodes) in enumerate(sections):
            body_html = "".join(str(n) for n in nodes)
            _make_chapter(idx, ch_title, body_html)
    else:
        _make_chapter(0, title or "Chapter 1", str(soup) or "<p></p>")

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters

    out = io.BytesIO()
    epub.write_epub(out, book)
    return out.getvalue()
