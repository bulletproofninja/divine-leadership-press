"""Provider-neutral print fulfillment and retail distribution rules."""

from typing import Any, Dict, List


PROVIDERS: List[Dict[str, Any]] = [
    {
        "key": "lulu",
        "name": "Lulu Direct",
        "mode": "print_fulfillment",
        "status": "setup_required",
        "capabilities": ["single_copy", "bulk", "direct_shipping", "tracking"],
        "description": "Print and ship customer orders directly from the storefront.",
    },
    {
        "key": "ingramspark",
        "name": "IngramSpark",
        "mode": "retail_distribution",
        "status": "package_export",
        "capabilities": ["bookstores", "libraries", "online_retailers", "global_catalog"],
        "description": "Prepare a complete title package for mainstream retail distribution.",
    },
]


def publishing_readiness(document: Dict[str, Any]) -> Dict[str, Any]:
    metadata = document.get("metadata") or {}
    checks = [
        ("manuscript", "Manuscript contains book content", len(_plain_text(document.get("content", ""))) >= 50),
        ("author", "Author name is supplied", bool(str(metadata.get("author") or "").strip())),
        ("description", "Book description is supplied", bool(str(metadata.get("description") or "").strip())),
        ("isbn", "ISBN is supplied for retail distribution", bool(str(metadata.get("isbn") or "").strip())),
        ("cover", "Cover artwork is attached", bool(document.get("cover_image_ext"))),
        ("interior_pdf", "Print interior PDF has been exported", bool(document.get("last_pdf_export_at"))),
        ("title", "Title is supplied", bool(str(metadata.get("title") or document.get("title") or "").strip())),
        ("publisher", "Publisher or imprint is supplied", bool(str(metadata.get("publisher") or "").strip())),
    ]
    items = [{"key": key, "label": label, "complete": complete} for key, label, complete in checks]
    direct_keys = {"manuscript", "author", "cover", "interior_pdf", "title"}
    retail_keys = direct_keys | {"description", "isbn", "publisher"}
    complete = {item["key"] for item in items if item["complete"]}
    return {
        "checks": items,
        "direct_print_ready": direct_keys.issubset(complete),
        "retail_distribution_ready": retail_keys.issubset(complete),
    }


def _plain_text(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", html or "").strip()

