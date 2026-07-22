from __future__ import annotations

import json
import pickle
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from product_support_agent.config import Settings
from product_support_agent.exceptions import MetadataError
from product_support_agent.logger import get_logger
from product_support_agent.models import ChunkRecord, UploadResult


class MetadataManager:
    """Persists upload manifests and vector-store chunk metadata."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = get_logger(__name__)

    @property
    def upload_manifest_path(self) -> Path:
        return self._settings.paths.upload_manifest_file

    @property
    def vector_metadata_path(self) -> Path:
        return self._settings.paths.vector_metadata_file

    def ensure_storage_files(self) -> None:
        self.upload_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.upload_manifest_path.exists():
            self.upload_manifest_path.write_text("[]", encoding="utf-8")

    def record_uploads(self, results: list[UploadResult]) -> None:
        if not results:
            return

        manifest = self.load_upload_manifest()
        manifest.extend(result.to_dict() for result in results)
        try:
            self.upload_manifest_path.write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise MetadataError("Unable to persist upload manifest.") from exc
        self._logger.info("Upload manifest updated successfully: entries=%s", len(manifest))

    def load_upload_manifest(self) -> list[dict[str, Any]]:
        self.ensure_storage_files()
        try:
            return json.loads(self.upload_manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise MetadataError("Unable to read upload manifest.") from exc

    def find_upload_by_checksum(self, checksum: str) -> dict[str, Any] | None:
        manifest = self.load_upload_manifest()
        for item in manifest:
            document_metadata = item.get("document_metadata") or {}
            if document_metadata.get("checksum") == checksum:
                return item
        return None

    def list_known_checksums(self) -> set[str]:
        manifest = self.load_upload_manifest()
        return {
            str(document_metadata.get("checksum"))
            for item in manifest
            for document_metadata in [item.get("document_metadata") or {}]
            if document_metadata.get("checksum")
        }

    def build_vector_store_records(
        self, chunks: list[ChunkRecord], start_vector_id: int
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for offset, chunk in enumerate(chunks):
            metadata = replace(chunk.metadata, vector_id=start_vector_id + offset)
            records.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": metadata.to_dict(),
                }
            )
        return records

    def create_empty_vector_state(self, embedding_model: str, dimension: int) -> dict[str, Any]:
        timestamp = datetime.now(UTC).isoformat()
        return {
            "embedding_model": embedding_model,
            "dimension": dimension,
            "created_at": timestamp,
            "updated_at": timestamp,
            "records": [],
        }

    def save_vector_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = datetime.now(UTC).isoformat()
        try:
            with self.vector_metadata_path.open("wb") as file_handle:
                pickle.dump(state, file_handle)
        except OSError as exc:
            raise MetadataError("Unable to write vector metadata file.") from exc
        self._logger.info(
            "Vector metadata saved successfully: records=%s",
            len(state.get("records", [])),
        )

    def load_vector_state(self) -> dict[str, Any] | None:
        if not self.vector_metadata_path.exists():
            return None
        try:
            with self.vector_metadata_path.open("rb") as file_handle:
                return pickle.load(file_handle)
        except Exception as exc:
            raise MetadataError("Unable to load vector metadata file.") from exc
