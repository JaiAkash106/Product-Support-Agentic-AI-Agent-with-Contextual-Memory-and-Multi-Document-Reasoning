from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from product_support_agent.models import ExtractedDocument


class BaseDocumentLoader(ABC):
    """Contract for a file-type-specific document loader."""

    supported_extension: str
    document_type: str

    @abstractmethod
    def load(self, file_path: Path) -> list[ExtractedDocument]:
        """Extract one or more logical documents from the given file."""
