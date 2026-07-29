from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class DocumentMetadata:
    file_name: str
    document_type: str
    file_path: Path
    file_size_bytes: int
    extension: str
    checksum: str
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["file_path"] = str(self.file_path)
        data["uploaded_at"] = self.uploaded_at.isoformat()
        return data


@dataclass(slots=True)
class ChatTurn:
    role: str
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ConversationMessage:
    role: str
    content: str
    grounded: bool | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "content": self.content,
            "grounded": self.grounded,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ConversationState:
    session_id: str
    messages: list[ConversationMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "messages": [message.to_dict() for message in self.messages],
        }


@dataclass(slots=True)
class ServiceStatus:
    name: str
    state: str
    details: str


@dataclass(slots=True)
class UploadPayload:
    file_name: str
    content: bytes


@dataclass(slots=True)
class UploadResult:
    original_file_name: str
    stored_file_name: str | None
    stored_path: Path | None
    file_size_bytes: int
    duplicate_strategy: str
    document_metadata: DocumentMetadata | None
    status: str = "processed"
    status_message: str = ""
    matched_existing_file_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "original_file_name": self.original_file_name,
            "stored_file_name": self.stored_file_name,
            "stored_path": str(self.stored_path) if self.stored_path is not None else None,
            "file_size_bytes": self.file_size_bytes,
            "duplicate_strategy": self.duplicate_strategy,
            "document_metadata": (
                self.document_metadata.to_dict()
                if self.document_metadata is not None
                else None
            ),
            "status": self.status,
            "status_message": self.status_message,
            "matched_existing_file_name": self.matched_existing_file_name,
        }


@dataclass(slots=True)
class ExtractedDocument:
    file_name: str
    document_type: str
    source_path: Path
    text: str
    page_number: int | None = None
    row_number: int | None = None
    extracted_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ChunkMetadata:
    file_name: str
    document_type: str
    chunk_number: int
    source_path: Path
    timestamp: str
    page_number: int | None = None
    row_number: int | None = None
    section_title: str | None = None
    vector_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "file_name": self.file_name,
            "document_type": self.document_type,
            "chunk_number": self.chunk_number,
            "source_path": str(self.source_path),
            "timestamp": self.timestamp,
            "page_number": self.page_number,
            "row_number": self.row_number,
            "section_title": self.section_title,
            "vector_id": self.vector_id,
        }


@dataclass(slots=True)
class ChunkRecord:
    chunk_id: str
    text: str
    metadata: ChunkMetadata

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(slots=True)
class IndexBuildResult:
    uploaded_files: int
    extracted_documents: int
    chunks_created: int
    vectors_in_index: int
    index_file: Path
    metadata_file: Path
    failed_files: list[str] = field(default_factory=list)
    duplicate_files: list[str] = field(default_factory=list)
    duplicate_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "uploaded_files": self.uploaded_files,
            "extracted_documents": self.extracted_documents,
            "chunks_created": self.chunks_created,
            "vectors_in_index": self.vectors_in_index,
            "index_file": str(self.index_file),
            "metadata_file": str(self.metadata_file),
            "failed_files": list(self.failed_files),
            "duplicate_files": list(self.duplicate_files),
            "duplicate_messages": list(self.duplicate_messages),
        }


@dataclass(slots=True)
class RetrievalResult:
    content: str
    score: float
    source_file: str
    source_path: Path
    page_number: int | None
    row_number: int | None
    chunk_number: int | None
    chunk_id: str
    document_type: str
    section_title: str | None = None
    rerank_score: float | None = None
    matched_terms: list[str] = field(default_factory=list)
    selection_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "score": self.score,
            "source_file": self.source_file,
            "source_path": str(self.source_path),
            "page_number": self.page_number,
            "row_number": self.row_number,
            "chunk_number": self.chunk_number,
            "chunk_id": self.chunk_id,
            "document_type": self.document_type,
            "section_title": self.section_title,
            "rerank_score": self.rerank_score,
            "matched_terms": list(self.matched_terms),
            "selection_reason": self.selection_reason,
        }


@dataclass(slots=True)
class RetrievalResponse:
    query: str
    top_k: int
    results: list[RetrievalResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "top_k": self.top_k,
            "results": [result.to_dict() for result in self.results],
        }


@dataclass(slots=True)
class SourceReference:
    file_name: str
    chunk_id: str
    page_number: int | None = None
    row_number: int | None = None
    chunk_number: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "file_name": self.file_name,
            "chunk_id": self.chunk_id,
            "page_number": self.page_number,
            "row_number": self.row_number,
            "chunk_number": self.chunk_number,
        }


@dataclass(slots=True)
class DocumentEvidenceSummary:
    file_name: str
    summary: str
    chunk_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "file_name": self.file_name,
            "summary": self.summary,
            "chunk_ids": list(self.chunk_ids),
        }


@dataclass(slots=True)
class RAGResponse:
    query: str
    answer: str
    sources: list[SourceReference]
    retrieved_results: list[RetrievalResult]
    grounded: bool
    selected_results: list[RetrievalResult] = field(default_factory=list)
    reasoning_strategy: str = "SIMPLE_QA"
    graph_nodes_executed: list[str] = field(default_factory=list)
    retrieved_chunk_count: int = 0
    relevant_chunk_count: int = 0
    source_documents: list[str] = field(default_factory=list)
    document_evidence: list[DocumentEvidenceSummary] = field(default_factory=list)
    resolved_query: str | None = None
    memory_messages_used: int = 0
    message: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "answer": self.answer,
            "sources": [source.to_dict() for source in self.sources],
            "retrieved_results": [
                retrieved_result.to_dict() for retrieved_result in self.retrieved_results
            ],
            "selected_results": [
                selected_result.to_dict() for selected_result in self.selected_results
            ],
            "grounded": self.grounded,
            "reasoning_strategy": self.reasoning_strategy,
            "graph_nodes_executed": list(self.graph_nodes_executed),
            "retrieved_chunk_count": self.retrieved_chunk_count,
            "relevant_chunk_count": self.relevant_chunk_count,
            "source_documents": list(self.source_documents),
            "document_evidence": [
                evidence.to_dict() for evidence in self.document_evidence
            ],
            "resolved_query": self.resolved_query,
            "memory_messages_used": self.memory_messages_used,
            "message": self.message,
            "error": self.error,
        }
