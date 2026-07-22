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
        else:  # pragma: no cover - explicit assertion guard
            raise AssertionError("Expected ValidationError for empty query.")


def test_retriever_rejects_whitespace_query(test_settings) -> None:
    retriever = RetrieverService(test_settings)

    try:
        retriever.retrieve("   ")
    except ValidationError as exc:
        assert "empty or whitespace only" in str(exc)
    else:  # pragma: no cover - explicit assertion guard
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
        else:  # pragma: no cover - explicit assertion guard
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
        else:  # pragma: no cover - explicit assertion guard
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
        else:  # pragma: no cover - explicit assertion guard
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
