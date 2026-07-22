from __future__ import annotations

import numpy as np

from product_support_agent.config import Settings
from product_support_agent.exceptions import IndexPersistenceError, ValidationError
from product_support_agent.logger import get_logger
from product_support_agent.models import RetrievalResponse, RetrievalResult, ServiceStatus
from product_support_agent.services.embedding_service import EmbeddingService
from product_support_agent.services.metadata_manager import MetadataManager
from product_support_agent.services.vector_store import VectorStoreService


class RetrieverService:
    """Validates queries and retrieves similar chunks from the persistent FAISS index."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = get_logger(__name__)
        self._embedding_service = EmbeddingService(settings)
        self._vector_store = VectorStoreService(settings, MetadataManager(settings))

    @property
    def top_k(self) -> int:
        return self._settings.app.top_k_results

    @property
    def max_query_length(self) -> int:
        return self._settings.app.max_query_length

    def validate_query(self, query: str) -> str:
        normalized_query = " ".join(query.split())
        self._logger.info("Validating retrieval query.")
        if not normalized_query:
            raise ValidationError("Query cannot be empty or whitespace only.")
        if len(normalized_query) > self.max_query_length:
            raise ValidationError(
                f"Query exceeds the maximum length of {self.max_query_length} characters."
            )
        return normalized_query

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResponse:
        normalized_query = self.validate_query(query)
        requested_top_k = top_k if top_k is not None else self.top_k
        if requested_top_k <= 0:
            raise ValidationError("Top-K must be greater than zero.")

        self._logger.info("Retrieval query received: query_length=%s", len(normalized_query))
        query_embedding = self._generate_query_embedding(normalized_query)
        distances, indices, state = self._vector_store.search(query_embedding, requested_top_k)

        records = state.get("records", [])
        results: list[RetrievalResult] = []
        for score, vector_index in zip(distances[0], indices[0], strict=False):
            if int(vector_index) < 0:
                continue
            if int(vector_index) >= len(records):
                raise IndexPersistenceError(
                    "Retrieved vector index is out of range for the stored metadata."
                )
            record = records[int(vector_index)]
            metadata = record.get("metadata", {})
            results.append(
                RetrievalResult(
                    content=str(record.get("text", "")),
                    score=float(score),
                    source_file=str(metadata.get("file_name", "")),
                    source_path=self._coerce_path(metadata.get("source_path")),
                    page_number=self._coerce_optional_int(metadata.get("page_number")),
                    row_number=self._coerce_optional_int(metadata.get("row_number")),
                    chunk_number=self._coerce_optional_int(metadata.get("chunk_number")),
                    chunk_id=str(record.get("chunk_id", "")),
                    document_type=str(metadata.get("document_type", "")),
                )
            )

        self._logger.info("Retrieval completed successfully: results_returned=%s", len(results))
        return RetrievalResponse(
            query=normalized_query,
            top_k=requested_top_k,
            results=results,
        )

    def _generate_query_embedding(self, query: str) -> np.ndarray:
        self._logger.info("Generating query embedding for retrieval.")
        embedding = self._embedding_service.embed_texts([query])
        return np.asarray(embedding, dtype="float32")

    @staticmethod
    def _coerce_path(value: object) -> "Path":
        from pathlib import Path

        return Path(str(value)) if value is not None else Path()

    @staticmethod
    def _coerce_optional_int(value: object) -> int | None:
        if value in (None, "", "None"):
            return None
        return int(value)

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="retriever",
            state="ready",
            details=(
                f"Retriever service is configured with top_k={self.top_k} and "
                f"max_query_length={self.max_query_length}."
            ),
        )
