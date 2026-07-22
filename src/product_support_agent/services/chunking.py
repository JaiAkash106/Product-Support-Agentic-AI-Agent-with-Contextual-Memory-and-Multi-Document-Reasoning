from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from product_support_agent.config import Settings
from product_support_agent.logger import get_logger
from product_support_agent.models import ChunkMetadata, ChunkRecord, ExtractedDocument, ServiceStatus
from product_support_agent.utils import utc_timestamp


class ChunkingService:
    """Splits extracted text into metadata-rich chunks."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = get_logger(__name__)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.app.chunk_size,
            chunk_overlap=settings.app.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    @property
    def chunk_size(self) -> int:
        return self._settings.app.chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._settings.app.chunk_overlap

    def chunk_documents(self, documents: list[ExtractedDocument]) -> list[ChunkRecord]:
        chunk_records: list[ChunkRecord] = []
        for document in documents:
            text_chunks = self._splitter.split_text(document.text)
            self._logger.info(
                "Chunking extracted document: file=%s document_type=%s produced_chunks=%s",
                document.file_name,
                document.document_type,
                len(text_chunks),
            )
            for chunk_number, text_chunk in enumerate(text_chunks, start=1):
                chunk_records.append(
                    ChunkRecord(
                        chunk_id=self._build_chunk_id(document, chunk_number),
                        text=text_chunk,
                        metadata=ChunkMetadata(
                            file_name=document.file_name,
                            document_type=document.document_type,
                            chunk_number=chunk_number,
                            page_number=document.page_number,
                            row_number=document.row_number,
                            source_path=document.source_path,
                            timestamp=utc_timestamp(),
                        ),
                    )
                )
        self._logger.info("Chunk generation completed: total_chunks=%s", len(chunk_records))
        return chunk_records

    def _build_chunk_id(self, document: ExtractedDocument, chunk_number: int) -> str:
        page_part = document.page_number if document.page_number is not None else "na"
        row_part = document.row_number if document.row_number is not None else "na"
        return f"{document.file_name}:{page_part}:{row_part}:{chunk_number}"

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="chunking",
            state="ready",
            details=(
                f"Recursive chunking is configured with chunk_size={self.chunk_size} "
                f"and chunk_overlap={self.chunk_overlap}."
            ),
        )
