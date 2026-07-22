from __future__ import annotations

from pathlib import Path

from product_support_agent.exceptions import ExtractionError, ValidationError
from product_support_agent.logger import get_logger
from product_support_agent.models import ExtractedDocument, ServiceStatus
from product_support_agent.services.loaders import (
    CSVDocumentLoader,
    PDFDocumentLoader,
    TXTDocumentLoader,
)


class DocumentLoader:
    """Facade that delegates loading to specialized file-type loaders."""

    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._loaders = {
            ".pdf": PDFDocumentLoader(),
            ".txt": TXTDocumentLoader(),
            ".csv": CSVDocumentLoader(),
        }

    def supported_extensions(self) -> tuple[str, ...]:
        return tuple(self._loaders.keys())

    def load_file(self, file_path: Path) -> list[ExtractedDocument]:
        extension = file_path.suffix.lower()
        loader = self._loaders.get(extension)
        if loader is None:
            raise ValidationError(f"Unsupported file type for loading: {file_path.name}")

        self._logger.info("Loading source document: %s", file_path)
        documents = loader.load(file_path)
        self._logger.info(
            "Completed document extraction: file=%s logical_documents=%s",
            file_path.name,
            len(documents),
        )
        return documents

    def load_files(self, file_paths: list[Path]) -> tuple[list[ExtractedDocument], list[str]]:
        extracted_documents: list[ExtractedDocument] = []
        failed_files: list[str] = []

        for file_path in file_paths:
            try:
                extracted_documents.extend(self.load_file(file_path))
            except (ExtractionError, ValidationError) as exc:
                self._logger.exception("Document extraction failed for %s", file_path.name)
                failed_files.append(str(exc))

        return extracted_documents, failed_files

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="document_loader",
            state="ready",
            details=(
                "Loader facade is configured for PDF, TXT, and CSV extraction "
                "with file-type-specific parsing strategies."
            ),
        )
