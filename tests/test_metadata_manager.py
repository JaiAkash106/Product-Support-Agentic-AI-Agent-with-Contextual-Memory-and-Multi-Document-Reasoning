from __future__ import annotations

from product_support_agent.models import (
    ChunkMetadata,
    ChunkRecord,
    DocumentMetadata,
    UploadResult,
)
from product_support_agent.services.metadata_manager import MetadataManager


def test_metadata_manager_persists_upload_manifest(test_settings) -> None:
    manager = MetadataManager(test_settings)
    manager.ensure_storage_files()

    upload_result = UploadResult(
        original_file_name="guide.txt",
        stored_file_name="guide.txt",
        stored_path=test_settings.paths.upload_dir / "guide.txt",
        file_size_bytes=128,
        duplicate_strategy="created",
        document_metadata=DocumentMetadata(
            file_name="guide.txt",
            document_type="txt",
            file_path=test_settings.paths.upload_dir / "guide.txt",
            file_size_bytes=128,
            extension=".txt",
            checksum="abc123",
        ),
    )

    manager.record_uploads([upload_result])
    manifest = manager.load_upload_manifest()

    assert len(manifest) == 1
    assert manifest[0]["stored_file_name"] == "guide.txt"


def test_metadata_manager_builds_chunk_records(test_settings) -> None:
    manager = MetadataManager(test_settings)
    chunk = ChunkRecord(
        chunk_id="guide.txt:na:na:1",
        text="Reset the router by holding the button for 10 seconds.",
        metadata=ChunkMetadata(
            file_name="guide.txt",
            document_type="txt",
            chunk_number=1,
            source_path=test_settings.paths.upload_dir / "guide.txt",
            timestamp="2026-07-06 00:00:00 UTC",
        ),
    )

    records = manager.build_vector_store_records([chunk], start_vector_id=3)

    assert records[0]["metadata"]["vector_id"] == 3
    assert records[0]["metadata"]["file_name"] == "guide.txt"
