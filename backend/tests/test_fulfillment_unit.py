from fulfillment import PROVIDERS, publishing_readiness


def _book(**overrides):
    book = {
        "title": "A Finished Book",
        "content": "<p>" + ("finished manuscript content " * 10) + "</p>",
        "metadata": {
            "title": "A Finished Book",
            "author": "Author Name",
            "description": "A complete description.",
            "isbn": "9780000000002",
            "publisher": "Divine Leadership Press",
        },
        "cover_image_ext": "png",
        "last_pdf_export_at": "2026-09-13T12:00:00+00:00",
    }
    book.update(overrides)
    return book


def test_provider_modes_are_separate():
    modes = {provider["key"]: provider["mode"] for provider in PROVIDERS}
    assert modes == {"lulu": "print_fulfillment", "ingramspark": "retail_distribution"}


def test_complete_book_is_ready_for_both_paths():
    result = publishing_readiness(_book())
    assert result["direct_print_ready"] is True
    assert result["retail_distribution_ready"] is True


def test_isbn_blocks_retail_but_not_direct_print():
    book = _book()
    book["metadata"]["isbn"] = ""
    result = publishing_readiness(book)
    assert result["direct_print_ready"] is True
    assert result["retail_distribution_ready"] is False


def test_cover_and_pdf_are_required_for_direct_print():
    result = publishing_readiness(_book(cover_image_ext=None, last_pdf_export_at=None))
    assert result["direct_print_ready"] is False
    incomplete = {item["key"] for item in result["checks"] if not item["complete"]}
    assert {"cover", "interior_pdf"}.issubset(incomplete)
