from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from product_support_agent.config import (
    AppSettings,
    LoggingSettings,
    PathSettings,
    Settings,
    ensure_runtime_directories,
)


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    faiss_dir = data_dir / "faiss"
    metadata_dir = data_dir / "metadata"
    upload_dir = data_dir / "uploads"
    log_dir = tmp_path / "logs"
    prompt_dir = tmp_path / "prompts"

    settings = Settings(
        paths=PathSettings(
            base_dir=tmp_path,
            src_dir=tmp_path / "src",
            data_dir=data_dir,
            upload_dir=upload_dir,
            faiss_dir=faiss_dir,
            metadata_dir=metadata_dir,
            log_dir=log_dir,
            prompt_dir=prompt_dir,
            default_prompt_file=prompt_dir / "system_prompt.txt",
            query_contextualization_prompt_file=prompt_dir
            / "query_contextualization_prompt.txt",
            document_summary_prompt_file=prompt_dir / "document_summary_prompt.txt",
            multi_document_synthesis_prompt_file=prompt_dir
            / "multi_document_synthesis_prompt.txt",
            vector_index_file=faiss_dir / "index.faiss",
            vector_metadata_file=faiss_dir / "index.pkl",
            upload_manifest_file=metadata_dir / "uploaded_files.json",
        ),
        logging=LoggingSettings(
            level="INFO",
            log_file=log_dir / "test.log",
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            date_format="%Y-%m-%d %H:%M:%S",
            max_bytes=1024 * 1024,
            backup_count=2,
        ),
        app=AppSettings(
            app_name="Test Product Support Agent",
            company_name="HCL",
            description="Test settings for the ingestion pipeline.",
            environment="test",
            debug=True,
            host="127.0.0.1",
            port=8501,
            page_title="Test",
            page_icon=":robot_face:",
            layout="wide",
            chunk_size=40,
            chunk_overlap=10,
            top_k_results=4,
            max_query_length=200,
            max_upload_size_mb=5,
            faiss_index_name="test_index",
            supported_extensions=(".pdf", ".txt", ".csv"),
            duplicate_upload_strategy="rename",
            embedding_model="all-MiniLM-L6-v2",
            embedding_batch_size=8,
            gemini_model="gemini-3.5-flash",
            gemini_api_key="",
            gemini_temperature=0.1,
            gemini_max_output_tokens=512,
            contextualizer_temperature=0.0,
            contextualizer_max_output_tokens=512,
            rag_relevance_threshold=0.35,
            rag_context_expansion_chunks=2,
            retrieval_candidate_pool_multiplier=5,
            retrieval_term_overlap_boost=0.18,
            retrieval_exact_match_boost=0.12,
            retrieval_section_title_boost=0.06,
            memory_max_turns=6,
        ),
    )
    ensure_runtime_directories(settings)
    return settings
