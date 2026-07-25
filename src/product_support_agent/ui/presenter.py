from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import streamlit as st

from product_support_agent.config import Settings
from product_support_agent.exceptions import ProductSupportAgentError
from product_support_agent.services.metadata_manager import MetadataManager


SEARCH_DEPTH_KEY = "ui_search_depth"
CLEAR_CONVERSATION_REQUEST_KEY = "ui_clear_conversation_requested"
CHAT_TRANSCRIPT_KEY = "ui_chat_transcript"
LAST_RAG_RESPONSE_KEY = "last_rag_response"


def get_search_depth(settings: Settings) -> int:
    if SEARCH_DEPTH_KEY not in st.session_state:
        st.session_state[SEARCH_DEPTH_KEY] = settings.app.top_k_results
    return int(st.session_state[SEARCH_DEPTH_KEY])


def request_clear_conversation() -> None:
    st.session_state[CLEAR_CONVERSATION_REQUEST_KEY] = True


def consume_clear_conversation_request() -> bool:
    return bool(st.session_state.pop(CLEAR_CONVERSATION_REQUEST_KEY, False))


def get_chat_transcript() -> list[dict[str, object]]:
    return list(st.session_state.get(CHAT_TRANSCRIPT_KEY, []))


def append_chat_record(record: dict[str, object]) -> None:
    transcript = get_chat_transcript()
    transcript.append(record)
    st.session_state[CHAT_TRANSCRIPT_KEY] = transcript


def clear_chat_transcript() -> None:
    st.session_state.pop(CHAT_TRANSCRIPT_KEY, None)


def build_sidebar_snapshot(settings: Settings) -> dict[str, object]:
    metadata_manager = MetadataManager(settings)
    manifest = _load_manifest(metadata_manager)
    vector_state = _load_vector_state(metadata_manager)

    indexed_documents = len(manifest)
    chunk_records = vector_state.get("records", []) if vector_state else []
    last_indexing_time = _derive_last_indexing_time(manifest, vector_state)

    provider = settings.app.llm_provider.strip().lower()
    model_name = (
        settings.app.ollama_model if provider == "ollama" else settings.app.gemini_model
    )
    provider_label = "Ollama" if provider == "ollama" else "Gemini"
    connected = _check_provider_connection(settings)

    transcript = get_chat_transcript()
    assistant_messages = [item for item in transcript if item.get("role") == "assistant"]
    last_response = st.session_state.get(LAST_RAG_RESPONSE_KEY, {}) or {}
    source_documents = last_response.get("source_documents", []) or []
    response_time_ms = last_response.get("response_time_ms")

    return {
        "indexed_documents": indexed_documents,
        "knowledge_chunks": len(chunk_records),
        "last_indexing_time": last_indexing_time,
        "provider": provider,
        "provider_label": provider_label,
        "model_name": model_name,
        "connected": connected,
        "memory_turns": len(assistant_messages),
        "search_depth": get_search_depth(settings),
        "retrieved_documents": len(source_documents),
        "response_time": _format_response_time(response_time_ms),
    }


def _load_manifest(metadata_manager: MetadataManager) -> list[dict[str, object]]:
    try:
        return metadata_manager.load_upload_manifest()
    except ProductSupportAgentError:
        return []


def _load_vector_state(metadata_manager: MetadataManager) -> dict[str, object] | None:
    try:
        return metadata_manager.load_vector_state()
    except ProductSupportAgentError:
        return None


def _derive_last_indexing_time(
    manifest: list[dict[str, object]],
    vector_state: dict[str, object] | None,
) -> str:
    timestamps: list[str] = []
    for item in manifest:
        document_metadata = item.get("document_metadata") or {}
        uploaded_at = document_metadata.get("uploaded_at")
        if isinstance(uploaded_at, str) and uploaded_at.strip():
            timestamps.append(uploaded_at)
    if vector_state and isinstance(vector_state.get("updated_at"), str):
        timestamps.append(str(vector_state["updated_at"]))
    if not timestamps:
        return "Not indexed yet"
    latest = max(timestamps)
    return _format_iso_time(latest)


def _format_iso_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%b %d, %Y %I:%M %p")


def _check_provider_connection(settings: Settings) -> bool:
    provider = settings.app.llm_provider.strip().lower()
    if provider == "ollama":
        try:
            with urlopen(f"{settings.app.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5) as resp:
                return 200 <= resp.status < 300
        except (OSError, URLError):
            return False
    return bool(settings.app.gemini_api_key.strip())


def _format_response_time(value: object) -> str:
    if value in (None, ""):
        return "Waiting"
    try:
        milliseconds = float(value)
    except (TypeError, ValueError):
        return "Waiting"
    if milliseconds < 1000:
        return f"{int(milliseconds)} ms"
    return f"{milliseconds / 1000:.1f} s"


def read_recent_logs(settings: Settings, *, limit: int = 40) -> list[tuple[str, str]]:
    log_path = Path(settings.logging.log_file)
    if not log_path.exists():
        return [("INFO", "No log file has been created yet.")]

    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return [("ERROR", "Unable to read the application log file.")]

    records: list[tuple[str, str]] = []
    for line in lines:
        level = "INFO"
        for candidate in ("ERROR", "WARNING", "INFO"):
            if f"| {candidate} |" in line:
                level = candidate
                break
        records.append((level, line))
    return records


def count_conversation_turns() -> int:
    transcript = get_chat_transcript()
    return len([item for item in transcript if item.get("role") == "assistant"])


def load_last_response() -> dict[str, object]:
    return dict(st.session_state.get(LAST_RAG_RESPONSE_KEY, {}) or {})
