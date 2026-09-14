"""
Image-to-PDF utilities — turn cover JPG/PNG/WebP into KDP-ready PDF covers.
"""
import io
from typing import Optional

from PIL import Image
from reportlab.lib.units import inch as INCH
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def _trim_to_points(trim_key: str) -> tuple:
    # Reuse our KDP trim catalogue but stay local to avoid a circular import.
    SIZES = {
        "5x8": (5.0, 8.0), "5.06x7.81": (5.06, 7.81), "5.25x8": (5.25, 8.0),
        "5.5x8.5": (5.5, 8.5), "6x9": (6.0, 9.0), "6.14x9.21": (6.14, 9.21),
        "6.69x9.61": (6.69, 9.61), "7x10": (7.0, 10.0), "7.44x9.69": (7.44, 9.69),
        "7.5x9.25": (7.5, 9.25), "8x10": (8.0, 10.0), "8.5x11": (8.5, 11.0),
    }
    w, h = SIZES.get(trim_key, SIZES["6x9"])
    return (w * INCH, h * INCH)


def image_to_pdf(
    *,
    image_bytes: bytes,
    trim_key: Optional[str] = "6x9",
    title: Optional[str] = "Cover",
    include_bleed: bool = False,
    bleed_inches: float = 0.125,
) -> bytes:
    """Render a proportional, edge-to-edge cover with optional printer bleed."""
    if not image_bytes:
        raise ValueError("No image data provided.")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not read image: {exc}")

    # Normalise to RGB (PDFs don't carry alpha well; flatten on white)
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    trim_w, trim_h = _trim_to_points(trim_key or "6x9")
    bleed = max(0.0, float(bleed_inches)) * INCH if include_bleed else 0
    page_w, page_h = trim_w + (2 * bleed), trim_h + (2 * bleed)
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=(page_w, page_h))
    c.setTitle(title or "Cover")

    # Scale image to cover the trim, centred, preserving aspect ratio (cover crop).
    iw, ih = img.size
    page_ratio = page_w / page_h
    img_ratio = iw / ih

    if img_ratio > page_ratio:
        # Image wider than page — fit by height, crop sides
        new_h = page_h
        new_w = page_h * img_ratio
    else:
        # Image taller — fit by width, crop top/bottom
        new_w = page_w
        new_h = page_w / img_ratio

    x = (page_w - new_w) / 2
    y = (page_h - new_h) / 2

    # Save image to in-memory JPEG for reportlab
    img_buf = io.BytesIO()
    img.save(img_buf, format="JPEG", quality=92)
    img_buf.seek(0)
    c.drawImage(
        ImageReader(img_buf),
        x, y, width=new_w, height=new_h,
        preserveAspectRatio=False,
    )
    c.showPage()
    c.save()
    return out.getvalue()
