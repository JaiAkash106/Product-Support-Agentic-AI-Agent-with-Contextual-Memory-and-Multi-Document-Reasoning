from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np

from product_support_agent.config import Settings
from product_support_agent.exceptions import IndexPersistenceError, MetadataError
from product_support_agent.logger import get_logger
from product_support_agent.models import ChunkRecord, ServiceStatus
from product_support_agent.services.metadata_manager import MetadataManager


class VectorStoreService:
    """Creates, loads, extends, and persists a local FAISS vector index."""

    def __init__(self, settings: Settings, metadata_manager: MetadataManager) -> None:
        self._settings = settings
        self._metadata_manager = metadata_manager
        self._logger = get_logger(__name__)

    @property
    def index_directory(self) -> Path:
        return self._settings.paths.faiss_dir

    @property
    def index_name(self) -> str:
        return self._settings.app.faiss_index_name

    @property
    def index_file(self) -> Path:
        return self._settings.paths.vector_index_file

    @property
    def metadata_file(self) -> Path:
        return self._settings.paths.vector_metadata_file

    def load_or_create_index(self, dimension: int) -> tuple[faiss.Index, dict]:
        if self.index_file.exists() and self.metadata_file.exists():
            try:
                index = faiss.read_index(str(self.index_file))
            except Exception as exc:  # pragma: no cover - faiss runtime failure path
                raise IndexPersistenceError("Unable to load existing FAISS index.") from exc

            try:
                state = self._metadata_manager.load_vector_state()
            except MetadataError as exc:
                raise IndexPersistenceError("Unable to load existing vector metadata.") from exc

            if state is None:
                raise IndexPersistenceError("Vector metadata file is missing or empty.")
            if int(state.get("dimension", 0)) != dimension:
                raise IndexPersistenceError(
                    "Existing FAISS index dimension does not match the embedding model output."
                )
            return index, state

        index = faiss.IndexFlatIP(dimension)
        state = self._metadata_manager.create_empty_vector_state(
            embedding_model=self._settings.app.embedding_model,
            dimension=dimension,
        )
        return index, state

    def add_embeddings(self, chunks: list[ChunkRecord], embeddings: np.ndarray) -> int:
        if len(chunks) != len(embeddings):
            raise IndexPersistenceError(
                "The number of chunk records does not match the number of embeddings."
            )
        if embeddings.size == 0:
            raise IndexPersistenceError("No embeddings were provided for FAISS persistence.")

        dimension = int(embeddings.shape[1])
        index, state = self.load_or_create_index(dimension)
        start_vector_id = int(index.ntotal)
        index.add(np.asarray(embeddings, dtype="float32"))

        records = self._metadata_manager.build_vector_store_records(chunks, start_vector_id)
        state["records"].extend(records)
        try:
            faiss.write_index(index, str(self.index_file))
            self._metadata_manager.save_vector_state(state)
        except Exception as exc:  # pragma: no cover - faiss runtime failure path
            raise IndexPersistenceError("Unable to persist FAISS index and metadata.") from exc

        self._logger.info(
            "FAISS index updated successfully: added_vectors=%s total_vectors=%s",
            len(chunks),
            index.ntotal,
        )
        return int(index.ntotal)

    def current_vector_count(self) -> int:
        if not self.index_file.exists() or not self.metadata_file.exists():
            return 0
        try:
            index = faiss.read_index(str(self.index_file))
        except Exception as exc:  # pragma: no cover - faiss runtime failure path
            raise IndexPersistenceError("Unable to load existing FAISS index.") from exc
        return int(index.ntotal)

    def load_existing_index_state(self) -> tuple[faiss.Index, dict]:
        if not self.index_file.exists() or not self.metadata_file.exists():
            raise IndexPersistenceError(
                "Persistent FAISS index files were not found. Build the knowledge base first."
            )

        try:
            index = faiss.read_index(str(self.index_file))
        except Exception as exc:  # pragma: no cover - faiss runtime failure path
            raise IndexPersistenceError("Unable to load existing FAISS index.") from exc

        try:
            state = self._metadata_manager.load_vector_state()
        except MetadataError as exc:
            raise IndexPersistenceError("Unable to load existing vector metadata.") from exc

        if state is None:
            raise IndexPersistenceError("Vector metadata file is missing or empty.")
        if int(index.ntotal) == 0:
            raise IndexPersistenceError(
                "Persistent FAISS index is empty. Ingest documents before retrieval."
            )

        records = state.get("records", [])
        if len(records) < int(index.ntotal):
            raise IndexPersistenceError(
                "Vector metadata is inconsistent with the FAISS index contents."
            )
        return index, state

    def search(self, query_vector: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray, dict]:
        if top_k <= 0:
            raise IndexPersistenceError("Top-K must be greater than zero for similarity search.")

        index, state = self.load_existing_index_state()
        try:
            distances, indices = index.search(
                np.asarray(query_vector, dtype="float32"),
                top_k,
            )
        except Exception as exc:  # pragma: no cover - faiss runtime failure path
            raise IndexPersistenceError("FAISS similarity search failed.") from exc
        return distances, indices, state

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="vector_store",
            state="ready",
            details=(
                f"Persistent FAISS storage is configured at {self.index_directory} "
                f"with index file {self.index_file.name}."
            ),
        )
