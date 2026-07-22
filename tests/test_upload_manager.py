from __future__ import annotations

from product_support_agent.services.metadata_manager import MetadataManager
from product_support_agent.models import UploadPayload
from product_support_agent.services.upload_manager import UploadManager


def test_upload_manager_saves_supported_files(test_settings) -> None:
    upload_manager = UploadManager(test_settings)

    results = upload_manager.save_files(
        [
            UploadPayload(file_name="sample.pdf", content=b"%PDF-1.4 fake"),
            UploadPayload(file_name="sample.txt", content=b"Product support notes"),
            UploadPayload(file_name="sample.csv", content=b"name,version\nrouter,2.0"),
        ]
    )

    assert len(results) == 3
    assert all(result.stored_path.exists() for result in results)
    assert {result.document_metadata.document_type for result in results} == {
        "pdf",
        "txt",
        "csv",
    }


def test_upload_manager_skips_same_filename_same_content(test_settings) -> None:
    upload_manager = UploadManager(test_settings)
    metadata_manager = MetadataManager(test_settings)
    first_payload = UploadPayload(file_name="duplicate.txt", content=b"first copy")

    first = upload_manager.save_file(first_payload)
    metadata_manager.record_uploads([first])
    second = upload_manager.save_file(first_payload)

    assert first.stored_file_name == "duplicate.txt"
    assert second.status == "duplicate_skipped"
    assert second.stored_file_name is None
    assert second.duplicate_strategy == "checksum_skip"


def test_upload_manager_skips_different_filename_same_content(test_settings) -> None:
    upload_manager = UploadManager(test_settings)
    metadata_manager = MetadataManager(test_settings)

    first = upload_manager.save_file(
        UploadPayload(file_name="original.txt", content=b"same content")
    )
    metadata_manager.record_uploads([first])
    second = upload_manager.save_file(
        UploadPayload(file_name="renamed.txt", content=b"same content")
    )

    assert second.status == "duplicate_skipped"
    assert second.stored_file_name is None


def test_upload_manager_renames_same_filename_different_content(test_settings) -> None:
    upload_manager = UploadManager(test_settings)
    metadata_manager = MetadataManager(test_settings)

    first = upload_manager.save_file(
        UploadPayload(file_name="duplicate.txt", content=b"first copy")
    )
    metadata_manager.record_uploads([first])
    second = upload_manager.save_file(
        UploadPayload(file_name="duplicate.txt", content=b"second copy")
    )

    assert second.status == "processed"
    assert second.stored_file_name is not None
    assert second.stored_file_name != "duplicate.txt"
    assert second.duplicate_strategy == "rename"
