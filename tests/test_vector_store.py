from __future__ import annotations

import numpy as np

from product_support_agent.models import ChunkMetadata, ChunkRecord
from product_support_agent.services.metadata_manager import MetadataManager
from product_support_agent.services.vector_store import VectorStoreService


def _make_chunk(file_name: str, chunk_number: int, source_path) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=f"{file_name}:na:na:{chunk_number}",
        text=f"chunk text {chunk_number}",
        metadata=ChunkMetadata(
            file_name=file_name,
            document_type="txt",
            chunk_number=chunk_number,
            source_path=source_path,
            timestamp="2026-07-06 00:00:00 UTC",
        ),
    )


def test_vector_store_persists_and_reloads_faiss_index(test_settings) -> None:
    metadata_manager = MetadataManager(test_settings)
    vector_store = VectorStoreService(test_settings, metadata_manager)

    chunks = [
        _make_chunk("guide.txt", 1, test_settings.paths.upload_dir / "guide.txt"),
        _make_chunk("guide.txt", 2, test_settings.paths.upload_dir / "guide.txt"),
    ]
    embeddings = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    first_total = vector_store.add_embeddings(chunks, embeddings)
    second_total = vector_store.add_embeddings(
        [_make_chunk("guide.txt", 3, test_settings.paths.upload_dir / "guide.txt")],
        np.asarray([[0.5, 0.5]], dtype=np.float32),
    )

    state = metadata_manager.load_vector_state()

    assert first_total == 2
    assert second_total == 3
    assert test_settings.paths.vector_index_file.exists()
    assert test_settings.paths.vector_metadata_file.exists()
    assert state is not None
    assert len(state["records"]) == 3
