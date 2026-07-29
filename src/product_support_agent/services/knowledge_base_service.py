from __future__ import annotations

from pathlib import Path

from product_support_agent.config import Settings
from product_support_agent.logger import get_logger
from product_support_agent.services.metadata_manager import MetadataManager


class KnowledgeBaseService:
    """Handles lifecycle operations for the persisted knowledge base."""

    def __init__(
        self,
        settings: Settings,
        *,
        metadata_manager: MetadataManager | None = None,
    ) -> None:
        self._settings = settings
        self._metadata_manager = metadata_manager or MetadataManager(settings)
        self._logger = get_logger(__name__)

    def clear(self) -> dict[str, int]:
        """Delete persisted uploads, FAISS files, and metadata, then recreate storage."""

        counts = {
            "deleted_files": 0,
            "deleted_directories": 0,
            "missing_paths": 0,
        }
        self._logger.info("Knowledge base clear started.")

        for target_dir in (
            self._settings.paths.upload_dir,
            self._settings.paths.faiss_dir,
            self._settings.paths.metadata_dir,
        ):
            self._clear_directory_contents(target_dir, counts)

        self._recreate_storage_layout()
        self._logger.info(
            "Knowledge base clear completed: deleted_files=%s deleted_directories=%s missing_paths=%s",
            counts["deleted_files"],
            counts["deleted_directories"],
            counts["missing_paths"],
        )
        return counts

    def _clear_directory_contents(self, directory: Path, counts: dict[str, int]) -> None:
        if not directory.exists():
            counts["missing_paths"] += 1
            self._logger.info(
                "Knowledge base clear skipped missing directory: path=%s",
                directory,
            )
            return

        for child in list(directory.iterdir()):
            self._delete_path(child, counts)

    def _delete_path(self, path: Path, counts: dict[str, int]) -> None:
        if not path.exists():
            counts["missing_paths"] += 1
            self._logger.info(
                "Knowledge base clear skipped missing path: path=%s",
                path,
            )
            return

        if path.is_dir():
            for child in list(path.iterdir()):
                self._delete_path(child, counts)
            try:
                path.rmdir()
            except OSError as exc:
                self._logger.warning(
                    "Knowledge base clear could not remove directory: path=%s error=%s",
                    path,
                    exc,
                )
                return
            counts["deleted_directories"] += 1
            self._logger.info("Knowledge base directory deleted: path=%s", path)
            return

        try:
            path.unlink()
        except OSError as exc:
            self._logger.warning(
                "Knowledge base clear could not remove file: path=%s error=%s",
                path,
                exc,
            )
            return
        counts["deleted_files"] += 1
        self._logger.info("Knowledge base file deleted: path=%s", path)

    def _recreate_storage_layout(self) -> None:
        for directory in (
            self._settings.paths.upload_dir,
            self._settings.paths.faiss_dir,
            self._settings.paths.metadata_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            self._logger.info("Knowledge base directory ensured: path=%s", directory)
        self._metadata_manager.ensure_storage_files()
        self._logger.info(
            "Knowledge base manifest reset: path=%s",
            self._settings.paths.upload_manifest_file,
        )
