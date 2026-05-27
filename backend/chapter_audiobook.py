"""
Per-chapter audiobook export.

Splits a manuscript at <h1>/<h2> headings and renders one MP3 per chapter,
then bundles them into a ZIP. Useful for KDP audiobook chapter uploads
and for distributors that require per-chapter files.
"""
from __future__ import annotations

import io
import re
import zipfile
from typing import List, Tuple

from bs4 import BeautifulSoup

from audio_narrator import narrate_audiobook, MAX_AUDIOBOOK_CHARS


CHAPTER_TAGS = ("h1", "h2")
MAX_CHAPTERS = 60


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("_")
    return base[:80] or "Chapter"


def split_into_chapters(html_content: str) -> List[Tuple[str, str]]:
    """Return [(chapter_title, chapter_html), ...].

    A new chapter starts at every <h1> or <h2>. Content before the first
    heading is treated as "Front Matter" if it has substance.
    """
    soup = BeautifulSoup(html_content or "", "html.parser")
    chapters: List[Tuple[str, str]] = []
    current_title = "Front Matter"
    current_parts: List[str] = []

    def _flush():
        nonlocal current_parts, current_title
        html = "".join(current_parts).strip()
        if html:
            text_check = BeautifulSoup(html, "html.parser").get_text(strip=True)
            if text_check:
                chapters.append((current_title, html))
        current_parts = []

    # Walk top-level children. Use body if available, otherwise the soup itself.
    container = soup.body if soup.body else soup
    for child in container.children:
        name = getattr(child, "name", None)
        if name and name.lower() in CHAPTER_TAGS:
            _flush()
            title_text = child.get_text(strip=True) or f"Chapter {len(chapters) + 1}"
            current_title = title_text
        else:
            # Preserve original HTML for fidelity (the narrator will strip later).
            if name is None:
                # Bare NavigableString
                text = str(child).strip()
                if text:
                    current_parts.append(f"<p>{text}</p>")
            else:
                current_parts.append(str(child))
    _flush()

    return chapters


async def export_chapters_zip(
    *,
    html_content: str,
    title: str,
    voice: str = "onyx",
    speed: float = 1.0,
) -> bytes:
    """Render one MP3 per chapter and bundle into a ZIP archive."""
    chapters = split_into_chapters(html_content)
    if not chapters:
        raise ValueError(
            "No chapters found. Use H1 or H2 headings to mark chapter boundaries."
        )
    if len(chapters) == 1:
        raise ValueError(
            "Only one chapter detected. Use H1 / H2 headings to mark chapter boundaries, "
            "or use the regular Audiobook export."
        )
    if len(chapters) > MAX_CHAPTERS:
        raise ValueError(
            f"This manuscript has {len(chapters)} chapters. Per-chapter export is limited "
            f"to {MAX_CHAPTERS} chapters per run."
        )

    # Pre-flight: every individual chapter must fit the single-shot audiobook limit.
    for ch_title, ch_html in chapters:
        plain = BeautifulSoup(ch_html, "html.parser").get_text(separator=" ", strip=True)
        if len(plain) > MAX_AUDIOBOOK_CHARS:
            raise ValueError(
                f"Chapter '{ch_title}' is {len(plain):,} characters — longer than the "
                f"{MAX_AUDIOBOOK_CHARS:,} character limit. Please split it into smaller sections."
            )

    safe_title = _safe_filename(title)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
        for idx, (ch_title, ch_html) in enumerate(chapters, start=1):
            mp3 = await narrate_audiobook(
                html_content=ch_html,
                voice=voice,
                speed=speed,
            )
            fname = f"{idx:02d}_{_safe_filename(ch_title)}.mp3"
            zf.writestr(fname, mp3)

        # Tiny tracklist for the listener / KDP uploader
        tracklist = "\n".join(
            f"{idx:02d}. {ch_title}" for idx, (ch_title, _) in enumerate(chapters, start=1)
        )
        zf.writestr(
            f"{safe_title}_tracklist.txt",
            f"Divine Leadership Press — per-chapter audiobook\n{title}\n\n{tracklist}\n",
        )

    return buf.getvalue()
