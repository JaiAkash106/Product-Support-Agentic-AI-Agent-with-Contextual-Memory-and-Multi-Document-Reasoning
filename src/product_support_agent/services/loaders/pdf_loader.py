from __future__ import annotations

import re
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
                text = self._extract_page_text(page).strip()
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

    def _extract_page_text(self, page: object) -> str:
        layout_text = ""
        try:
            layout_text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            layout_text = page.extract_text() or ""

        if layout_text.strip():
            return self._normalize_extracted_text(layout_text)

        plain_text = page.extract_text() or ""
        return self._normalize_extracted_text(plain_text)

    def _normalize_extracted_text(self, text: str) -> str:
        normalized_lines: list[str] = []
        previous_blank = True

        for raw_line in text.splitlines():
            stripped_line = raw_line.strip()
            if not stripped_line:
                if not previous_blank:
                    normalized_lines.append("")
                previous_blank = True
                continue

            if self._looks_like_table_row(raw_line):
                parts = [
                    self._normalize_inline_text(part)
                    for part in re.split(r"\s{2,}", stripped_line)
                    if part.strip()
                ]
                normalized_line = " | ".join(parts)
            else:
                normalized_line = self._normalize_inline_text(stripped_line)

            normalized_lines.append(normalized_line)
            previous_blank = False

        return "\n".join(normalized_lines).strip()

    @staticmethod
    def _normalize_inline_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _looks_like_table_row(raw_line: str) -> bool:
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("•"):
            return False

        columns = [part.strip() for part in re.split(r"\s{2,}", stripped_line) if part.strip()]
        if len(columns) < 2 or len(columns) > 5:
            return False

        if max(len(part) for part in columns) > 80:
            return False

        return True
