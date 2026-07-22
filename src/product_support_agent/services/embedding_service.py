from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from product_support_agent.config import Settings
from product_support_agent.exceptions import EmbeddingError
from product_support_agent.logger import get_logger
from product_support_agent.models import ServiceStatus


class EmbeddingService:
    """Generates local embeddings using SentenceTransformers."""

    def __init__(self, settings: Settings, model_name: str | None = None) -> None:
        self._settings = settings
        self._model_name = model_name or settings.app.embedding_model
        self._logger = get_logger(__name__)
        self._model: SentenceTransformer | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._logger.info("Loading local embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            raise EmbeddingError("No text chunks were supplied for embedding generation.")

        self._logger.info(
            "Generating local embeddings: model=%s chunk_count=%s",
            self.model_name,
            len(texts),
        )
        try:
            embeddings = self._get_model().encode(
                texts,
                batch_size=self._settings.app.embedding_batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:  # pragma: no cover - model/runtime failure path
            raise EmbeddingError("Embedding generation failed.") from exc

        self._logger.info(
            "Embedding generation completed: vector_count=%s vector_dimension=%s",
            len(embeddings),
            int(embeddings.shape[1]),
        )
        return np.asarray(embeddings, dtype="float32")

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="embedding_service",
            state="ready",
            details=(
                "Local embedding generation is configured with model "
                f"{self.model_name}."
            ),
        )
