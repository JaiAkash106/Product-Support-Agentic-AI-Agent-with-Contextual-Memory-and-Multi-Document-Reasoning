from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from product_support_agent.services.document_loader import DocumentLoader
from product_support_agent.services.loaders.csv_loader import CSVDocumentLoader
from product_support_agent.services.loaders.pdf_loader import PDFDocumentLoader
from product_support_agent.services.loaders.txt_loader import TXTDocumentLoader


def test_txt_loader_extracts_text(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Router reset instructions", encoding="utf-8")

    documents = TXTDocumentLoader().load(file_path)

    assert len(documents) == 1
    assert documents[0].text == "Router reset instructions"
    assert documents[0].document_type == "txt"


def test_csv_loader_extracts_rows(tmp_path: Path) -> None:
    file_path = tmp_path / "matrix.csv"
    file_path.write_text("product,version\nrouter,2.0\nswitch,3.1", encoding="utf-8")

    documents = CSVDocumentLoader().load(file_path)

    assert len(documents) == 2
    assert documents[0].row_number == 1
    assert "product: router" in documents[0].text


def test_pdf_loader_extracts_pages_with_mock(tmp_path: Path) -> None:
    file_path = tmp_path / "manual.pdf"
    file_path.write_bytes(b"%PDF-1.4")

    page_one = Mock()
    page_one.extract_text.return_value = "First page content"
    page_two = Mock()
    page_two.extract_text.return_value = "Second page content"
    fake_reader = Mock()
    fake_reader.pages = [page_one, page_two]

    with patch(
        "product_support_agent.services.loaders.pdf_loader.PdfReader",
        return_value=fake_reader,
    ):
        documents = PDFDocumentLoader().load(file_path)

    assert len(documents) == 2
    assert documents[0].page_number == 1
    assert documents[1].page_number == 2


def test_document_loader_facade_loads_multiple_files(tmp_path: Path) -> None:
    txt_path = tmp_path / "guide.txt"
    txt_path.write_text("Support guide", encoding="utf-8")
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("name,status\nrouter,active", encoding="utf-8")

    documents, failures = DocumentLoader().load_files([txt_path, csv_path])

    assert failures == []
    assert len(documents) == 2
