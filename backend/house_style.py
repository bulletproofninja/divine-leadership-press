"""Author-protective editorial policy shared by every DLP AI tool."""

EM_DASH = "\u2014"

EDITORIAL_POLICY = """DIVINE LEADERSHIP PRESS HOUSE RULES:
- Preserve the author's wording, meaning, doctrine, claims, examples, and voice.
- Do not make substantive changes unless the author's current instruction clearly asks for rewriting or new prose.
- For proofreading or copy editing, propose only necessary mechanical corrections.
- Never use an em dash. Use a comma, colon, semicolon, parentheses, or a new sentence.
- Do not alter exact quotations or legally fixed language. Flag a concern instead.
- Never invent facts, citations, names, dates, or quotations.
"""


def remove_em_dashes(text: str) -> str:
    """Guarantee that newly generated AI text follows the no-em-dash rule."""
    return (text or "").replace(EM_DASH, ";")


def follows_house_style(text: str) -> bool:
    return EM_DASH not in (text or "")
