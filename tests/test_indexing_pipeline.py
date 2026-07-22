from __future__ import annotations

from unittest.mock import patch

import numpy as np

from product_support_agent.models import UploadPayload
from product_support_agent.services.indexing_pipeline import KnowledgeBaseIngestionPipeline
from product_support_agent.services.metadata_manager import MetadataManager


def test_indexing_pipeline_builds_local_knowledge_base(test_settings) -> None:
    pipeline = KnowledgeBaseIngestionPipeline(test_settings)

    payloads = [
        UploadPayload(
            file_name="guide.txt",
            content=b"Reset procedure. Hold the reset button for ten seconds.",
        ),
        UploadPayload(
            file_name="matrix.csv",
            content=b"product,version\nrouter,2.0\nswitch,3.1",
        ),
    ]

    with patch(
        "product_support_agent.services.indexing_pipeline.EmbeddingService.embed_texts",
        side_effect=lambda texts: np.ones((len(texts), 6), dtype=np.float32),
    ):
        result = pipeline.ingest_uploads(payloads)

    state = MetadataManager(test_settings).load_vector_state()

    assert result.uploaded_files == 2
    assert result.extracted_documents >= 2
    assert result.chunks_created >= 2
    assert result.vectors_in_index >= 2
    assert state is not None
    assert len(state["records"]) == result.vectors_in_index


def test_indexing_pipeline_second_ingestion_skips_duplicate_and_keeps_vector_count(
    test_settings,
) -> None:
    pipeline = KnowledgeBaseIngestionPipeline(test_settings)
    payload = UploadPayload(
        file_name="guide.txt",
        content=b"Reset procedure. Hold the reset button for ten seconds.",
    )

    with patch(
        "product_support_agent.services.indexing_pipeline.EmbeddingService.embed_texts",
        side_effect=lambda texts: np.ones((len(texts), 6), dtype=np.float32),
    ):
        first_result = pipeline.ingest_uploads([payload])
        second_result = pipeline.ingest_uploads([payload])

    assert first_result.vectors_in_index > 0
    assert second_result.uploaded_files == 0
    assert second_result.extracted_documents == 0
    assert second_result.chunks_created == 0
    assert second_result.vectors_in_index == first_result.vectors_in_index
    assert second_result.duplicate_messages == [
        "Duplicate document skipped because this content already exists in the knowledge base."
    ]


def test_indexing_pipeline_uses_persistent_manifest_after_restart(test_settings) -> None:
    first_pipeline = KnowledgeBaseIngestionPipeline(test_settings)
    second_pipeline = KnowledgeBaseIngestionPipeline(test_settings)
    payload = UploadPayload(
        file_name="guide.txt",
        content=b"Reset procedure. Hold the reset button for ten seconds.",
    )

    with patch(
        "product_support_agent.services.indexing_pipeline.EmbeddingService.embed_texts",
        side_effect=lambda texts: np.ones((len(texts), 6), dtype=np.float32),
    ):
        first_result = first_pipeline.ingest_uploads([payload])
        second_result = second_pipeline.ingest_uploads(
            [UploadPayload(file_name="guide-again.txt", content=payload.content)]
        )

    assert first_result.vectors_in_index > 0
    assert second_result.uploaded_files == 0
    assert second_result.vectors_in_index == first_result.vectors_in_index
    assert second_result.duplicate_files == ["guide-again.txt"]
