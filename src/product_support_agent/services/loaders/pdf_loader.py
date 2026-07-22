from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from product_support_agent.exceptions import ExtractionError
from product_support_agent.logger import get_logger
from product_support_agent.models import ExtractedDocument
from product_support_agent.services.loaders.base import BaseDocumentLoader


class PDFDocumentLoader(BaseDocumentLoader):
    """Extracts text from PDF files page by page."""

    supported_extension = ".pdf"
    document_type = "pdf"

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    def load(self, file_path: Path) -> list[ExtractedDocument]:
        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:  # pragma: no cover - library-specific failure path
            raise ExtractionError(f"Unable to open PDF file: {file_path.name}") from exc

        extracted_pages: list[ExtractedDocument] = []
        for page_index, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception as exc:  # pragma: no cover - library-specific failure path
                raise ExtractionError(
                    f"Failed to extract text from PDF page {page_index} in {file_path.name}"
                ) from exc

            if not text:
                self._logger.warning(
                    "Skipping empty PDF page during extraction: file=%s page=%s",
                    file_path.name,
                    page_index,
                )
                continue

            extracted_pages.append(
                ExtractedDocument(
                    file_name=file_path.name,
                    document_type=self.document_type,
                    source_path=file_path,
                    text=text,
                    page_number=page_index,
                )
            )

        if not extracted_pages:
            raise ExtractionError(
                f"No extractable text was found in PDF file {file_path.name}."
            )

        return extracted_pages
