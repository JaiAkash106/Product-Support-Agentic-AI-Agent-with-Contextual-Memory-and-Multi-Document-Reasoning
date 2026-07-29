from __future__ import annotations

import json

from product_support_agent.services.knowledge_base_service import KnowledgeBaseService
from product_support_agent.services.metadata_manager import MetadataManager


def test_knowledge_base_service_clears_persisted_storage_and_reinitializes_manifest(
    test_settings,
) -> None:
    upload_file = test_settings.paths.upload_dir / "guide.txt"
    upload_file.write_text("Reset steps", encoding="utf-8")

    nested_directory = test_settings.paths.upload_dir / "nested"
    nested_directory.mkdir(parents=True, exist_ok=True)
    (nested_directory / "notes.txt").write_text("Nested note", encoding="utf-8")

    test_settings.paths.vector_index_file.write_text("faiss", encoding="utf-8")
    test_settings.paths.vector_metadata_file.write_text("metadata", encoding="utf-8")
    (test_settings.paths.metadata_dir / "chunks.json").write_text("[]", encoding="utf-8")
    test_settings.paths.upload_manifest_file.write_text(
        json.dumps([{"file_name": "guide.txt"}]),
        encoding="utf-8",
    )

    service = KnowledgeBaseService(test_settings)

    result = service.clear()

    assert result["deleted_files"] >= 5
    assert result["deleted_directories"] >= 1
    assert test_settings.paths.upload_dir.exists()
    assert test_settings.paths.faiss_dir.exists()
    assert test_settings.paths.metadata_dir.exists()
    assert list(test_settings.paths.upload_dir.iterdir()) == []
    assert list(test_settings.paths.faiss_dir.iterdir()) == []
    assert MetadataManager(test_settings).load_upload_manifest() == []


def test_knowledge_base_service_handles_missing_storage_gracefully(test_settings) -> None:
    for directory in (
        test_settings.paths.upload_dir,
        test_settings.paths.faiss_dir,
        test_settings.paths.metadata_dir,
    ):
        if directory.exists():
            for child in directory.iterdir():
                if child.is_dir():
                    for nested_child in child.rglob("*"):
                        if nested_child.is_file():
                            nested_child.unlink()
                    for nested_dir in sorted(
                        [item for item in child.rglob("*") if item.is_dir()],
                        reverse=True,
                    ):
                        nested_dir.rmdir()
                    child.rmdir()
                else:
                    child.unlink()
            directory.rmdir()

    service = KnowledgeBaseService(test_settings)

    result = service.clear()

    assert result["missing_paths"] >= 3
    assert test_settings.paths.upload_dir.exists()
    assert test_settings.paths.faiss_dir.exists()
    assert test_settings.paths.metadata_dir.exists()
    assert MetadataManager(test_settings).load_upload_manifest() == []
