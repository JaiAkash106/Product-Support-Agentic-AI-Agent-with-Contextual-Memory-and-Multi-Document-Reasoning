from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    items = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    return items or default


@dataclass(frozen=True)
class PathSettings:
    base_dir: Path
    src_dir: Path
    data_dir: Path
    upload_dir: Path
    faiss_dir: Path
    metadata_dir: Path
    log_dir: Path
    prompt_dir: Path
    default_prompt_file: Path
    query_contextualization_prompt_file: Path
    document_summary_prompt_file: Path
    multi_document_synthesis_prompt_file: Path
    vector_index_file: Path
    vector_metadata_file: Path
    upload_manifest_file: Path


@dataclass(frozen=True)
class LoggingSettings:
    level: str
    log_file: Path
    format: str
    date_format: str
    max_bytes: int
    backup_count: int


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    company_name: str
    description: str
    environment: str
    debug: bool
    host: str
    port: int
    page_title: str
    page_icon: str
    layout: str
    chunk_size: int
    chunk_overlap: int
    top_k_results: int
    max_query_length: int
    max_upload_size_mb: int
    faiss_index_name: str
    supported_extensions: tuple[str, ...]
    duplicate_upload_strategy: str
    embedding_model: str
    embedding_batch_size: int
    gemini_model: str
    gemini_api_key: str
    gemini_temperature: float
    gemini_max_output_tokens: int
    contextualizer_temperature: float
    contextualizer_max_output_tokens: int
    rag_relevance_threshold: float
    rag_context_expansion_chunks: int
    memory_max_turns: int


@dataclass(frozen=True)
class Settings:
    paths: PathSettings
    logging: LoggingSettings
    app: AppSettings


def _build_paths() -> PathSettings:
    data_dir = BASE_DIR / "data"
    prompt_dir = BASE_DIR / "prompts"
    metadata_dir = data_dir / "metadata"
    faiss_dir = data_dir / "faiss"
    return PathSettings(
        base_dir=BASE_DIR,
        src_dir=BASE_DIR / "src",
        data_dir=data_dir,
        upload_dir=data_dir / "uploads",
        faiss_dir=faiss_dir,
        metadata_dir=metadata_dir,
        log_dir=BASE_DIR / "logs",
        prompt_dir=prompt_dir,
        default_prompt_file=prompt_dir / "system_prompt.txt",
        query_contextualization_prompt_file=prompt_dir / "query_contextualization_prompt.txt",
        document_summary_prompt_file=prompt_dir / "document_summary_prompt.txt",
        multi_document_synthesis_prompt_file=prompt_dir
        / "multi_document_synthesis_prompt.txt",
        vector_index_file=faiss_dir / os.getenv("FAISS_INDEX_FILE", "index.faiss"),
        vector_metadata_file=faiss_dir / os.getenv("FAISS_METADATA_FILE", "index.pkl"),
        upload_manifest_file=metadata_dir
        / os.getenv("UPLOAD_MANIFEST_FILE", "uploaded_files.json"),
    )


def _build_logging(paths: PathSettings) -> LoggingSettings:
    return LoggingSettings(
        level=os.getenv("APP_LOG_LEVEL", "INFO").upper(),
        log_file=paths.log_dir / "product_support_agent.log",
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        date_format="%Y-%m-%d %H:%M:%S",
        max_bytes=5 * 1024 * 1024,
        backup_count=5,
    )


def _build_app() -> AppSettings:
    return AppSettings(
        app_name="Product Support Agentic AI Agent with Contextual Memory and Multi-Document Reasoning",
        company_name="HCL",
        description=(
            "Enterprise foundation for a product support assistant with modular "
            "services, centralized configuration, and a Streamlit application shell."
        ),
        environment=os.getenv("APP_ENV", "development"),
        debug=_get_bool("APP_DEBUG", True),
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=_get_int("APP_PORT", 8501),
        page_title="Product Support Agentic AI",
        page_icon=":robot_face:",
        layout="wide",
        chunk_size=_get_int("CHUNK_SIZE", 1000),
        chunk_overlap=_get_int("CHUNK_OVERLAP", 200),
        top_k_results=_get_int("TOP_K_RESULTS", 4),
        max_query_length=_get_int("MAX_QUERY_LENGTH", 500),
        max_upload_size_mb=_get_int("MAX_UPLOAD_SIZE_MB", 50),
        faiss_index_name="product_support_index",
        supported_extensions=_get_list(
            "SUPPORTED_FILE_TYPES", (".pdf", ".txt", ".csv")
        ),
        duplicate_upload_strategy=os.getenv("DUPLICATE_UPLOAD_STRATEGY", "rename"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        embedding_batch_size=_get_int("EMBEDDING_BATCH_SIZE", 32),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""),
        gemini_temperature=_get_float("GEMINI_TEMPERATURE", 0.1),
        gemini_max_output_tokens=_get_int("GEMINI_MAX_OUTPUT_TOKENS", 512),
        contextualizer_temperature=_get_float("CONTEXTUALIZER_TEMPERATURE", 0.0),
        contextualizer_max_output_tokens=_get_int(
            "CONTEXTUALIZER_MAX_OUTPUT_TOKENS",
            512,
        ),
        rag_relevance_threshold=_get_float("RAG_RELEVANCE_THRESHOLD", 0.35),
        rag_context_expansion_chunks=_get_int("RAG_CONTEXT_EXPANSION_CHUNKS", 2),
        memory_max_turns=_get_int("MEMORY_MAX_TURNS", 6),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    paths = _build_paths()
    return Settings(
        paths=paths,
        logging=_build_logging(paths),
        app=_build_app(),
    )


def ensure_runtime_directories(settings: Settings) -> None:
    directories = (
        settings.paths.data_dir,
        settings.paths.upload_dir,
        settings.paths.faiss_dir,
        settings.paths.metadata_dir,
        settings.paths.log_dir,
        settings.paths.prompt_dir,
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
