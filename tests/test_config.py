from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from product_support_agent.config import get_settings


def test_settings_defaults_are_loaded() -> None:
    settings = get_settings()

    assert settings.app.chunk_size == 1000
    assert settings.app.chunk_overlap == 200
    assert settings.app.top_k_results == 4
    assert settings.app.max_query_length == 500
    assert settings.app.supported_extensions == (".pdf", ".txt", ".csv")
    assert settings.paths.upload_dir.name == "uploads"
    assert settings.paths.faiss_dir.name == "faiss"
    assert settings.paths.metadata_dir.name == "metadata"
