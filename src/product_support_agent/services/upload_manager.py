from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from product_support_agent.config import Settings
from product_support_agent.exceptions import ValidationError
from product_support_agent.logger import get_logger
from product_support_agent.models import (
    DocumentMetadata,
    ServiceStatus,
    UploadPayload,
    UploadResult,
)
from product_support_agent.services.metadata_manager import MetadataManager


class UploadManager:
    """Validates, de-duplicates, and persists uploaded source files."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = get_logger(__name__)
        self._metadata_manager = MetadataManager(settings)

    def supported_extensions(self) -> tuple[str, ...]:
        return self._settings.app.supported_extensions

    def validate(self, payload: UploadPayload) -> None:
        extension = Path(payload.file_name).suffix.lower()
        if extension not in self.supported_extensions():
            raise ValidationError(
                f"Unsupported file type '{extension}' for file {payload.file_name}."
            )

        if not payload.content:
            raise ValidationError(f"Uploaded file {payload.file_name} is empty.")

        max_size_bytes = self._settings.app.max_upload_size_mb * 1024 * 1024
        if len(payload.content) > max_size_bytes:
            raise ValidationError(
                f"File {payload.file_name} exceeds the maximum size of "
                f"{self._settings.app.max_upload_size_mb} MB."
            )

    def save_files(self, payloads: list[UploadPayload]) -> list[UploadResult]:
        results: list[UploadResult] = []
        known_checksums = self._metadata_manager.list_known_checksums()
        batch_checksums: set[str] = set()
        for payload in payloads:
            checksum = hashlib.sha256(payload.content).hexdigest()
            if checksum in known_checksums or checksum in batch_checksums:
                results.append(
                    self._build_duplicate_result(
                        payload=payload,
                        checksum=checksum,
                    )
                )
                continue

            result = self.save_file(
                payload,
                checksum=checksum,
                manifest_lookup_required=False,
            )
            if result.status == "processed":
                batch_checksums.add(checksum)
            results.append(result)
        return results

    def save_file(
        self,
        payload: UploadPayload,
        checksum: str | None = None,
        manifest_lookup_required: bool = True,
    ) -> UploadResult:
        self.validate(payload)

        original_name = Path(payload.file_name).name
        checksum = checksum or hashlib.sha256(payload.content).hexdigest()
        if manifest_lookup_required:
            existing_upload = self._metadata_manager.find_upload_by_checksum(checksum)
            if existing_upload is not None:
                return self._build_duplicate_result(
                    payload=payload,
                    checksum=checksum,
                    existing_upload=existing_upload,
                )

        target_path, duplicate_strategy = self._resolve_target_path(original_name)
        target_path.write_bytes(payload.content)

        document_metadata = DocumentMetadata(
            file_name=target_path.name,
            document_type=target_path.suffix.lower().lstrip("."),
            file_path=target_path,
            file_size_bytes=len(payload.content),
            extension=target_path.suffix.lower(),
            checksum=checksum,
        )
        result = UploadResult(
            original_file_name=original_name,
            stored_file_name=target_path.name,
            stored_path=target_path,
            file_size_bytes=len(payload.content),
            duplicate_strategy=duplicate_strategy,
            document_metadata=document_metadata,
            status="processed",
            status_message="Document saved and accepted for ingestion.",
        )

        self._logger.info(
            "Upload saved successfully: file=%s stored_as=%s strategy=%s",
            original_name,
            target_path.name,
            duplicate_strategy,
        )
        return result

    def _build_duplicate_result(
        self,
        payload: UploadPayload,
        checksum: str,
        existing_upload: dict[str, object] | None = None,
    ) -> UploadResult:
        original_name = Path(payload.file_name).name
        if existing_upload is None:
            existing_upload = self._metadata_manager.find_upload_by_checksum(checksum)
        existing_document_metadata = (existing_upload or {}).get("document_metadata") or {}
        existing_file_name = (
            (existing_upload or {}).get("stored_file_name")
            or existing_document_metadata.get("file_name")
            or original_name
        )
        status_message = (
            "Duplicate document skipped because this content already exists in the "
            "knowledge base."
        )
        self._logger.info(
            "Upload skipped as duplicate: file=%s existing_file=%s checksum=%s",
            original_name,
            existing_file_name,
            checksum,
        )
        return UploadResult(
            original_file_name=original_name,
            stored_file_name=None,
            stored_path=None,
            file_size_bytes=len(payload.content),
            duplicate_strategy="checksum_skip",
            document_metadata=None,
            status="duplicate_skipped",
            status_message=status_message,
            matched_existing_file_name=str(existing_file_name),
        )

    def _resolve_target_path(self, file_name: str) -> tuple[Path, str]:
        base_path = self._settings.paths.upload_dir / file_name
        if not base_path.exists():
            return base_path, "created"

        strategy = self._settings.app.duplicate_upload_strategy.lower()
        if strategy == "overwrite":
            return base_path, "overwrite"
        if strategy == "error":
            raise ValidationError(
                f"A file named {file_name} already exists in the upload directory."
            )
        if strategy != "rename":
            raise ValidationError(
                f"Unsupported duplicate upload strategy: {strategy}."
            )

        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        renamed_path = base_path.with_name(
            f"{base_path.stem}_{timestamp}{base_path.suffix}"
        )
        collision_counter = 1
        while renamed_path.exists():
            renamed_path = base_path.with_name(
                f"{base_path.stem}_{timestamp}_{collision_counter}{base_path.suffix}"
            )
            collision_counter += 1
        return renamed_path, "rename"

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="upload_manager",
            state="ready",
            details=(
                "Upload validation, duplicate handling, and file persistence are configured."
            ),
        )
