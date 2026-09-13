from io import BytesIO

from PIL import Image
from PyPDF2 import PdfReader

from cover_spread import calculate_cover_dimensions, generate_cover_spread


def _png(color: str) -> bytes:
    image = Image.new("RGB", (1800, 2700), color)
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def test_kdp_cream_spine_and_wrap_dimensions():
    dimensions = calculate_cover_dimensions("6x9", 200, "cream")
    assert dimensions.spine_width == 0.5
    assert dimensions.cover_width == 12.75
    assert dimensions.cover_height == 9.25
    assert dimensions.spine_text_allowed


def test_spine_text_is_disabled_below_eighty_pages():
    dimensions = calculate_cover_dimensions("6x9", 79, "black_white")
    assert not dimensions.spine_text_allowed


def test_generated_wrap_pdf_uses_calculated_media_box():
    pdf_bytes, dimensions = generate_cover_spread(
        front_image_bytes=_png("navy"),
        back_image_bytes=_png("#f6f0df"),
        trim_key="6x9",
        page_count=200,
        paper_type="cream",
        title="Test Book",
        author="Test Author",
    )
    page = PdfReader(BytesIO(pdf_bytes)).pages[0]
    assert round(float(page.mediabox.width) / 72, 2) == dimensions.cover_width
    assert round(float(page.mediabox.height) / 72, 2) == dimensions.cover_height
