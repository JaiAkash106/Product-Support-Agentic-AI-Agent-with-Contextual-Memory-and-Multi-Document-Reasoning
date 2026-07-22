from __future__ import annotations

from pathlib import Path

from product_support_agent.exceptions import ExtractionError
from product_support_agent.models import ExtractedDocument
from product_support_agent.services.loaders.base import BaseDocumentLoader


class TXTDocumentLoader(BaseDocumentLoader):
    """Extracts text from plain text files."""

    supported_extension = ".txt"
    document_type = "txt"

    def load(self, file_path: Path) -> list[ExtractedDocument]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            raise ExtractionError(f"Unable to read TXT file: {file_path.name}") from exc

        if not text:
            raise ExtractionError(f"TXT file {file_path.name} does not contain usable text.")

        return [
            ExtractedDocument(
                file_name=file_path.name,
                document_type=self.document_type,
                source_path=file_path,
                text=text,
            )
        ]
