from __future__ import annotations

from product_support_agent.services.loaders.pdf_loader import PDFDocumentLoader


def test_pdf_loader_normalizes_layout_text_for_table_rows() -> None:
    loader = PDFDocumentLoader()

    normalized_text = loader._normalize_extracted_text(
        "Programming Language                Version\n"
        "Python                  3.8.0\n"
        "\n"
        "\u2022    There  are  two  hands-on  coding  questions.\n"
    )

    assert "Programming Language | Version" in normalized_text
    assert "Python | 3.8.0" in normalized_text
    assert "\u2022 There are two hands-on coding questions." in normalized_text
