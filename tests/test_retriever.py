from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import faiss
import numpy as np

from product_support_agent.exceptions import IndexPersistenceError, ValidationError
from product_support_agent.models import ChunkMetadata, ChunkRecord
from product_support_agent.services.metadata_manager import MetadataManager
from product_support_agent.services.retriever import RetrieverService
from product_support_agent.services.vector_store import VectorStoreService


def _make_chunk(
    *,
    file_name: str,
    chunk_number: int,
    text: str,
    source_path: Path,
    page_number: int | None = None,
    section_title: str | None = None,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=f"{file_name}:{page_number if page_number is not None else 'na'}:na:{chunk_number}",
        text=text,
        metadata=ChunkMetadata(
            file_name=file_name,
            document_type="pdf",
            chunk_number=chunk_number,
            page_number=page_number,
            source_path=source_path,
            section_title=section_title,
            timestamp="2026-07-18 00:00:00 UTC",
        ),
    )


def _seed_retrieval_index(test_settings) -> None:
    metadata_manager = MetadataManager(test_settings)
    vector_store = VectorStoreService(test_settings, metadata_manager)
    chunks = [
        _make_chunk(
            file_name="manual.pdf",
            chunk_number=1,
            text="Router reset procedure and safety steps.",
            source_path=test_settings.paths.upload_dir / "manual.pdf",
            page_number=1,
        ),
        _make_chunk(
            file_name="manual.pdf",
            chunk_number=2,
            text="Warranty and compliance notes.",
            source_path=test_settings.paths.upload_dir / "manual.pdf",
            page_number=2,
        ),
        _make_chunk(
            file_name="guide.pdf",
            chunk_number=1,
            text="Advanced switch configuration guidance.",
            source_path=test_settings.paths.upload_dir / "guide.pdf",
            page_number=3,
        ),
    ]
    embeddings = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.7, 0.1, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    vector_store.add_embeddings(chunks, embeddings)


def test_retriever_rejects_empty_query(test_settings) -> None:
    retriever = RetrieverService(test_settings)

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
    ):
        try:
            retriever.retrieve("")
        except ValidationError as exc:
            assert "empty or whitespace only" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected ValidationError for empty query.")


def test_retriever_rejects_whitespace_query(test_settings) -> None:
    retriever = RetrieverService(test_settings)

    try:
        retriever.retrieve("   ")
    except ValidationError as exc:
        assert "empty or whitespace only" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValidationError for whitespace query.")


def test_retriever_returns_top_k_results_with_metadata(test_settings) -> None:
    _seed_retrieval_index(test_settings)
    retriever = RetrieverService(test_settings)

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
    ):
        response = retriever.retrieve("router reset procedure", top_k=2)

    assert response.top_k == 2
    assert len(response.results) == 2
    assert response.results[0].source_file == "manual.pdf"
    assert response.results[0].page_number == 1
    assert response.results[0].chunk_number == 1
    assert response.results[0].chunk_id.endswith(":1")
    assert response.results[0].score >= response.results[1].score


def test_retriever_respects_top_k(test_settings) -> None:
    _seed_retrieval_index(test_settings)
    retriever = RetrieverService(test_settings)

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
    ):
        response = retriever.retrieve("router", top_k=1)

    assert len(response.results) == 1


def test_retriever_raises_for_missing_faiss_index(test_settings) -> None:
    retriever = RetrieverService(test_settings)

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
    ):
        try:
            retriever.retrieve("router")
        except IndexPersistenceError as exc:
            assert "were not found" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected IndexPersistenceError for missing index.")


def test_retriever_raises_for_empty_index(test_settings) -> None:
    metadata_manager = MetadataManager(test_settings)
    state = metadata_manager.create_empty_vector_state(
        embedding_model=test_settings.app.embedding_model,
        dimension=3,
    )
    metadata_manager.save_vector_state(state)
    faiss.write_index(faiss.IndexFlatIP(3), str(test_settings.paths.vector_index_file))
    retriever = RetrieverService(test_settings)

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
    ):
        try:
            retriever.retrieve("router")
        except IndexPersistenceError as exc:
            assert "is empty" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected IndexPersistenceError for empty index.")


def test_retriever_detects_query_embedding_dimension_mismatch(test_settings) -> None:
    _seed_retrieval_index(test_settings)
    retriever = RetrieverService(test_settings)

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[1.0, 0.0]], dtype=np.float32),
    ):
        try:
            retriever.retrieve("router")
        except IndexPersistenceError as exc:
            assert "similarity search failed" in str(exc).lower()
        else:  # pragma: no cover
            raise AssertionError("Expected IndexPersistenceError for dimension mismatch.")


def test_retriever_works_after_restart(test_settings) -> None:
    _seed_retrieval_index(test_settings)
    first_retriever = RetrieverService(test_settings)
    second_retriever = RetrieverService(test_settings)

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[0.0, 1.0, 0.0]], dtype=np.float32),
    ):
        first_response = first_retriever.retrieve("switch", top_k=1)
        second_response = second_retriever.retrieve("switch", top_k=1)

    assert first_response.results[0].source_file == "guide.pdf"
    assert second_response.results[0].source_file == "guide.pdf"


def test_retriever_reranks_exact_match_chunks_and_populates_diagnostics(test_settings) -> None:
    retriever = RetrieverService(test_settings)
    state = {
        "records": [
            {
                "chunk_id": "deep-learning.pdf:131:na:3",
                "text": "The algorithm may break ties when values are identical.",
                "metadata": {
                    "file_name": "deep-learning.pdf",
                    "source_path": str(test_settings.paths.upload_dir / "deep-learning.pdf"),
                    "page_number": 131,
                    "row_number": None,
                    "chunk_number": 3,
                    "document_type": "pdf",
                    "section_title": "Nearest Neighbor",
                },
            },
            {
                "chunk_id": "Subject Specific Instructions_PNQT.pdf:1:na:1",
                "text": (
                    "Advanced Coding Easy | 35\n"
                    "Breaktime | 1\n"
                    "Advanced Coding Medium | 55"
                ),
                "metadata": {
                    "file_name": "Subject Specific Instructions_PNQT.pdf",
                    "source_path": str(
                        test_settings.paths.upload_dir / "Subject Specific Instructions_PNQT.pdf"
                    ),
                    "page_number": 1,
                    "row_number": None,
                    "chunk_number": 1,
                    "document_type": "pdf",
                    "section_title": "SUBJECT SPECIFIC INSTRUCTIONS",
                },
            },
        ]
    }

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
    ), patch.object(
        retriever._vector_store,
        "search",
        return_value=(
            np.asarray([[0.33, 0.19]], dtype=np.float32),
            np.asarray([[0, 1]], dtype=np.int64),
            state,
        ),
    ):
        response = retriever.retrieve("Breaktime", top_k=1)

    top_result = response.results[0]
    assert top_result.source_file == "Subject Specific Instructions_PNQT.pdf"
    assert top_result.section_title == "SUBJECT SPECIFIC INSTRUCTIONS"
    assert top_result.rerank_score is not None
    assert top_result.rerank_score > top_result.score
    assert top_result.matched_terms == ["breaktime"]
    assert "matched terms: breaktime" in top_result.selection_reason


def test_retriever_expands_adjacent_chapter_content_and_deduplicates_headers(
    test_settings,
) -> None:
    retriever = RetrieverService(test_settings)
    state = {
        "records": [
            {
                "chunk_id": "Deep+Learning+Ian+Goodfellow.pdf:731:na:1",
                "text": "CHAPTER | 20. | DEEP | GENERATIVE | MODELS",
                "metadata": {
                    "file_name": "Deep+Learning+Ian+Goodfellow.pdf",
                    "source_path": str(
                        test_settings.paths.upload_dir / "Deep+Learning+Ian+Goodfellow.pdf"
                    ),
                    "page_number": 731,
                    "row_number": None,
                    "chunk_number": 1,
                    "document_type": "pdf",
                    "section_title": None,
                },
            },
            {
                "chunk_id": "Deep+Learning+Ian+Goodfellow.pdf:731:na:2",
                "text": (
                    "Generative models can provide answers to inference problems and "
                    "learn hierarchical representations of the world."
                ),
                "metadata": {
                    "file_name": "Deep+Learning+Ian+Goodfellow.pdf",
                    "source_path": str(
                        test_settings.paths.upload_dir / "Deep+Learning+Ian+Goodfellow.pdf"
                    ),
                    "page_number": 731,
                    "row_number": None,
                    "chunk_number": 2,
                    "document_type": "pdf",
                    "section_title": None,
                },
            },
            {
                "chunk_id": "Deep+Learning+Ian+Goodfellow.pdf:728:na:1",
                "text": "CHAPTER | 20. | DEEP | GENERATIVE | MODELS",
                "metadata": {
                    "file_name": "Deep+Learning+Ian+Goodfellow.pdf",
                    "source_path": str(
                        test_settings.paths.upload_dir / "Deep+Learning+Ian+Goodfellow.pdf"
                    ),
                    "page_number": 728,
                    "row_number": None,
                    "chunk_number": 1,
                    "document_type": "pdf",
                    "section_title": None,
                },
            },
            {
                "chunk_id": "Deep+Learning+Ian+Goodfellow.pdf:736:na:7",
                "text": (
                    "Generative models hold the promise to provide AI systems with a "
                    "framework for intuitive concepts they need to understand."
                ),
                "metadata": {
                    "file_name": "Deep+Learning+Ian+Goodfellow.pdf",
                    "source_path": str(
                        test_settings.paths.upload_dir / "Deep+Learning+Ian+Goodfellow.pdf"
                    ),
                    "page_number": 736,
                    "row_number": None,
                    "chunk_number": 7,
                    "document_type": "pdf",
                    "section_title": None,
                },
            },
        ]
    }

    with patch.object(
        RetrieverService,
        "_generate_query_embedding",
        return_value=np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
    ), patch.object(
        retriever._vector_store,
        "search",
        return_value=(
            np.asarray([[0.80, 0.79, 0.74]], dtype=np.float32),
            np.asarray([[0, 2, 3]], dtype=np.int64),
            state,
        ),
    ):
        response = retriever.retrieve(
            "Give me three important points from the Deep Generative Models chapter",
            top_k=3,
        )

    assert len(response.results) == 3
    assert response.results[0].chunk_id == "Deep+Learning+Ian+Goodfellow.pdf:736:na:7"
    assert sum(
        1 for result in response.results if result.content == "CHAPTER | 20. | DEEP | GENERATIVE | MODELS"
    ) == 1
    assert any(
        result.chunk_id == "Deep+Learning+Ian+Goodfellow.pdf:731:na:2"
        and "adjacent chunk expansion" in result.selection_reason
        for result in response.results
    )
