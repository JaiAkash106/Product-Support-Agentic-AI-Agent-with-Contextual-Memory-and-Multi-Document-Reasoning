from __future__ import annotations

from unittest.mock import patch

import numpy as np

from product_support_agent.services.embedding_service import EmbeddingService


class _FakeSentenceTransformer:
    def encode(self, texts, **kwargs):
        return np.ones((len(texts), 8), dtype=np.float32)


def test_embedding_service_generates_embeddings(test_settings) -> None:
    with patch(
        "product_support_agent.services.embedding_service.SentenceTransformer",
        return_value=_FakeSentenceTransformer(),
    ):
        service = EmbeddingService(test_settings)
        embeddings = service.embed_texts(["alpha", "beta"])

    assert embeddings.shape == (2, 8)
    assert embeddings.dtype == np.float32
