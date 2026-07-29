from __future__ import annotations

import re
from dataclasses import replace

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

    _TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
    _STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "between",
        "by",
        "discuss",
        "discusses",
        "do",
        "does",
        "document",
        "explain",
        "explains",
        "for",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "there",
        "to",
        "what",
        "which",
        "with",
    }

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

    @property
    def candidate_pool_multiplier(self) -> int:
        return max(1, self._settings.app.retrieval_candidate_pool_multiplier)

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
        candidate_top_k = max(requested_top_k, requested_top_k * self.candidate_pool_multiplier)
        distances, indices, state = self._vector_store.search(query_embedding, candidate_top_k)

        records = state.get("records", [])
        candidate_results: list[RetrievalResult] = []
        for score, vector_index in zip(distances[0], indices[0], strict=False):
            if int(vector_index) < 0:
                continue
            if int(vector_index) >= len(records):
                raise IndexPersistenceError(
                    "Retrieved vector index is out of range for the stored metadata."
                )
            record = records[int(vector_index)]
            candidate_results.append(self._build_result(record=record, score=float(score)))

        reranked_results = self._rerank_results(normalized_query, candidate_results)
        results = reranked_results[:requested_top_k]

        self._logger.info(
            "Retrieval completed successfully: candidate_results=%s results_returned=%s",
            len(candidate_results),
            len(results),
        )
        return RetrievalResponse(
            query=normalized_query,
            top_k=requested_top_k,
            results=results,
        )

    def _generate_query_embedding(self, query: str) -> np.ndarray:
        self._logger.info("Generating query embedding for retrieval.")
        embedding = self._embedding_service.embed_texts([query])
        return np.asarray(embedding, dtype="float32")

    def _build_result(self, *, record: dict[str, object], score: float) -> RetrievalResult:
        metadata = record.get("metadata", {})
        return RetrievalResult(
            content=str(record.get("text", "")),
            score=score,
            source_file=str(metadata.get("file_name", "")),
            source_path=self._coerce_path(metadata.get("source_path")),
            page_number=self._coerce_optional_int(metadata.get("page_number")),
            row_number=self._coerce_optional_int(metadata.get("row_number")),
            chunk_number=self._coerce_optional_int(metadata.get("chunk_number")),
            chunk_id=str(record.get("chunk_id", "")),
            document_type=str(metadata.get("document_type", "")),
            section_title=self._coerce_optional_text(metadata.get("section_title")),
        )

    def _rerank_results(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        query_terms = self._extract_query_terms(query)
        enriched_results = [
            self._enrich_result_with_ranking(query=query, query_terms=query_terms, result=result)
            for result in results
        ]
        return sorted(
            enriched_results,
            key=lambda result: (
                result.rerank_score if result.rerank_score is not None else result.score,
                result.score,
            ),
            reverse=True,
        )

    def _enrich_result_with_ranking(
        self,
        *,
        query: str,
        query_terms: list[str],
        result: RetrievalResult,
    ) -> RetrievalResult:
        searchable_text = " ".join(
            part
            for part in (
                result.source_file.replace("_", " "),
                result.section_title or "",
                result.content,
            )
            if part
        )
        normalized_text = " ".join(searchable_text.lower().split())
        indexed_terms = set(self._extract_query_terms(searchable_text))
        matched_terms = sorted(
            {
                term
                for term in query_terms
                if term in indexed_terms or term in normalized_text
            }
        )

        overlap_ratio = (
            len(matched_terms) / len(query_terms)
            if query_terms
            else 0.0
        )
        section_terms = set(self._extract_query_terms(result.section_title or ""))
        section_overlap = (
            len([term for term in query_terms if term in section_terms]) / len(query_terms)
            if query_terms
            else 0.0
        )
        exact_match = " ".join(query.lower().split()) in normalized_text

        rerank_score = (
            result.score
            + overlap_ratio * self._settings.app.retrieval_term_overlap_boost
            + section_overlap * self._settings.app.retrieval_section_title_boost
            + (
                self._settings.app.retrieval_exact_match_boost
                if exact_match
                else 0.0
            )
        )

        reason_parts = [f"semantic similarity {result.score:.4f}"]
        if matched_terms:
            reason_parts.append(f"matched terms: {', '.join(matched_terms)}")
        if result.section_title:
            reason_parts.append(f"section: {result.section_title}")
        if exact_match:
            reason_parts.append("exact phrase overlap")

        return replace(
            result,
            rerank_score=rerank_score,
            matched_terms=matched_terms,
            selection_reason="; ".join(reason_parts),
        )

    def _extract_query_terms(self, value: str) -> list[str]:
        normalized_tokens = [
            token
            for token in self._TOKEN_PATTERN.findall(value.lower())
            if token and token not in self._STOP_WORDS and len(token) > 1
        ]
        return list(dict.fromkeys(normalized_tokens))

    @staticmethod
    def _coerce_path(value: object) -> "Path":
        from pathlib import Path

        return Path(str(value)) if value is not None else Path()

    @staticmethod
    def _coerce_optional_int(value: object) -> int | None:
        if value in (None, "", "None"):
            return None
        return int(value)

    @staticmethod
    def _coerce_optional_text(value: object) -> str | None:
        if value in (None, "", "None"):
            return None
        return str(value)

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="retriever",
            state="ready",
            details=(
                f"Retriever service is configured with top_k={self.top_k} and "
                f"max_query_length={self.max_query_length}."
            ),
        )
