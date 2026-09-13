"""KDP paperback full-wrap cover calculations and PDF rendering."""

import io
from dataclasses import asdict, dataclass

from PIL import Image
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from exporters import KDP_TRIM_SIZES

BLEED_INCHES = 0.125
SPINE_FACTORS = {
    "black_white": 0.002252,
    "cream": 0.0025,
    "groundwood": 0.00235,
    "standard_color": 0.002252,
    "premium_color": 0.002347,
}


@dataclass(frozen=True)
class CoverDimensions:
    trim_width: float
    trim_height: float
    page_count: int
    paper_type: str
    spine_width: float
    cover_width: float
    cover_height: float
    bleed: float = BLEED_INCHES
    spine_text_allowed: bool = False

    def to_dict(self) -> dict:
        return {key: round(value, 4) if isinstance(value, float) else value for key, value in asdict(self).items()}


def calculate_cover_dimensions(trim_key: str, page_count: int, paper_type: str) -> CoverDimensions:
    if trim_key not in KDP_TRIM_SIZES:
        raise ValueError("Choose a supported trim size.")
    if paper_type not in SPINE_FACTORS:
        raise ValueError("Choose a supported paper and ink type.")
    if not 24 <= int(page_count) <= 828:
        raise ValueError("Paperback page count must be between 24 and 828.")
    trim_width, trim_height = KDP_TRIM_SIZES[trim_key]
    spine_width = int(page_count) * SPINE_FACTORS[paper_type]
    return CoverDimensions(
        trim_width=trim_width,
        trim_height=trim_height,
        page_count=int(page_count),
        paper_type=paper_type,
        spine_width=spine_width,
        cover_width=(2 * trim_width) + spine_width + (2 * BLEED_INCHES),
        cover_height=trim_height + (2 * BLEED_INCHES),
        spine_text_allowed=int(page_count) >= 80 and spine_width >= 0.222,
    )


def _load_rgb(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as exc:
        raise ValueError(f"Could not read cover artwork: {exc}") from exc
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.split()[-1])
        return background
    return image.convert("RGB")


def _draw_cover_crop(pdf, image: Image.Image, x: float, y: float, width: float, height: float) -> None:
    image_ratio = image.width / image.height
    box_ratio = width / height
    if image_ratio > box_ratio:
        draw_height = height
        draw_width = height * image_ratio
    else:
        draw_width = width
        draw_height = width / image_ratio
    left = x + ((width - draw_width) / 2)
    bottom = y + ((height - draw_height) / 2)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    pdf.saveState()
    clipping_path = pdf.beginPath()
    clipping_path.rect(x, y, width, height)
    pdf.clipPath(clipping_path, stroke=0, fill=0)
    pdf.drawImage(ImageReader(buffer), left, bottom, draw_width, draw_height, preserveAspectRatio=False)
    pdf.restoreState()


def generate_cover_spread(
    *,
    front_image_bytes: bytes,
    back_image_bytes: bytes,
    trim_key: str,
    page_count: int,
    paper_type: str,
    title: str = "",
    author: str = "",
    reserve_barcode: bool = True,
) -> tuple[bytes, CoverDimensions]:
    dimensions = calculate_cover_dimensions(trim_key, page_count, paper_type)
    front = _load_rgb(front_image_bytes)
    back = _load_rgb(back_image_bytes)
    page_width = dimensions.cover_width * inch
    page_height = dimensions.cover_height * inch
    bleed = dimensions.bleed * inch
    trim_width = dimensions.trim_width * inch
    spine_width = dimensions.spine_width * inch

    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(page_width, page_height))
    pdf.setTitle(f"{title or 'Book'}: Full Cover")
    pdf.setFillColorRGB(0.043, 0.114, 0.227)
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    _draw_cover_crop(pdf, back, 0, 0, bleed + trim_width, page_height)
    front_x = bleed + trim_width + spine_width
    _draw_cover_crop(pdf, front, front_x, 0, trim_width + bleed, page_height)

    if reserve_barcode:
        barcode_width = 2 * inch
        barcode_height = 1.2 * inch
        barcode_x = bleed + trim_width - barcode_width - (0.25 * inch)
        barcode_y = bleed + (0.25 * inch)
        pdf.setFillColorRGB(1, 1, 1)
        pdf.rect(barcode_x, barcode_y, barcode_width, barcode_height, fill=1, stroke=0)

    if dimensions.spine_text_allowed and title:
        center_x = bleed + trim_width + (spine_width / 2)
        pdf.saveState()
        pdf.translate(center_x, page_height / 2)
        pdf.rotate(90)
        font_size = max(7, min(12, (spine_width / inch - 0.125) * 72))
        pdf.setFont("Times-Bold", font_size)
        pdf.setFillColorRGB(1, 0.965, 0.86)
        spine_label = title if not author else f"{title}  |  {author}"
        pdf.drawCentredString(0, -(font_size / 3), spine_label)
        pdf.restoreState()

    pdf.showPage()
    pdf.save()
    return output.getvalue(), dimensions
