from __future__ import annotations

from collections import Counter

import streamlit as st

from product_support_agent.config import Settings
from product_support_agent.exceptions import ProductSupportAgentError
from product_support_agent.services.metadata_manager import MetadataManager
from product_support_agent.ui.presenter import (
    SEARCH_DEPTH_KEY,
    get_search_depth,
    load_last_response,
    request_clear_conversation,
)


def render_sidebar(settings: Settings, snapshot: dict[str, object]) -> None:
    st.sidebar.markdown("## Product Support AI")
    st.sidebar.caption("Your private document assistant")

    st.sidebar.markdown("### Workspace")
    st.sidebar.markdown("**Knowledge Base**")
    st.sidebar.markdown(f"Documents  \n`{snapshot['indexed_documents']}`")
    st.sidebar.markdown(f"Chunks  \n`{snapshot['knowledge_chunks']}`")
    st.sidebar.markdown(f"Last Updated  \n{snapshot['last_indexing_time']}")

    st.sidebar.markdown("### AI Status")
    st.sidebar.markdown(f"Provider  \n`{snapshot['provider_label']}`")
    st.sidebar.markdown(f"Model  \n`{snapshot['model_name']}`")
    st.sidebar.markdown(
        f"Status  \n{'Connected' if snapshot['connected'] else 'Offline'}"
    )

    st.sidebar.markdown("### Conversation")
    st.sidebar.markdown(f"Turns  \n`{snapshot['memory_turns']}`")
    st.sidebar.slider(
        "Search Depth",
        min_value=1,
        max_value=20,
        value=get_search_depth(settings),
        key=SEARCH_DEPTH_KEY,
        help="Higher values search more knowledge before the assistant answers.",
    )
    if st.sidebar.button("Clear Conversation", type="secondary", use_container_width=True):
        request_clear_conversation()

    with st.sidebar.expander("Developer Tools", expanded=False):
        _render_developer_tools(settings)


def _render_developer_tools(settings: Settings) -> None:
    metadata_manager = MetadataManager(settings)
    last_response = load_last_response()

    if not last_response:
        st.info("The latest answer details will appear here after the assistant responds.")
        return

    _render_latest_sources(last_response)
    _render_latest_debug(last_response)
    _render_latest_retrieval(last_response)
    _render_latest_metadata(settings, metadata_manager, last_response)


def _render_latest_sources(last_response: dict[str, object]) -> None:
    with st.expander("Sources", expanded=False):
        sources = last_response.get("sources", [])
        retrieved_results = last_response.get("retrieved_results", [])
        results_by_chunk = {
            str(item.get("chunk_id", "")): item
            for item in retrieved_results
            if isinstance(item, dict)
        }
        if not sources:
            st.info("No source citations are available for the latest answer.")
            return

        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                continue
            chunk_id = str(source.get("chunk_id", ""))
            result = results_by_chunk.get(chunk_id, {})
            st.markdown(f"**Source {index}**  \n{source.get('file_name', 'Unknown file')}")
            st.caption(_build_location_caption_from_source(source))
            if result.get("score") is not None:
                st.caption(f"Similarity {float(result['score']):.4f}")
            preview = str(result.get("content", "")).strip()
            if preview:
                st.write(preview[:320] + ("..." if len(preview) > 320 else ""))


def _render_latest_debug(last_response: dict[str, object]) -> None:
    with st.expander("Debug Information", expanded=False):
        st.json(
            {
                "query": last_response.get("query"),
                "resolved_query": last_response.get("resolved_query"),
                "memory_messages_used": last_response.get("memory_messages_used"),
                "reasoning_strategy": last_response.get("reasoning_strategy"),
                "graph_nodes_executed": last_response.get("graph_nodes_executed"),
                "retrieved_chunk_count": last_response.get("retrieved_chunk_count"),
                "relevant_chunk_count": last_response.get("relevant_chunk_count"),
                "source_documents": last_response.get("source_documents"),
                "response_time_ms": last_response.get("response_time_ms"),
                "pipeline_information": {
                    "graph_nodes_executed": last_response.get("graph_nodes_executed"),
                    "reasoning_strategy": last_response.get("reasoning_strategy"),
                },
                "message": last_response.get("message"),
                "error": last_response.get("error"),
            }
        )


def _render_latest_retrieval(last_response: dict[str, object]) -> None:
    with st.expander("Retrieval Details", expanded=False):
        retrieved_results = last_response.get("retrieved_results", [])
        if not retrieved_results:
            st.info("No retrieval details are available for the latest answer.")
            return

        for index, result in enumerate(retrieved_results, start=1):
            if not isinstance(result, dict):
                continue
            st.markdown(
                f"**Result {index}**  \n{result.get('source_file', 'Unknown file')}"
            )
            st.caption(_build_location_caption(result.get("page_number"), result.get("row_number"), result.get("chunk_number")))
            score = result.get("score")
            if score is not None:
                st.caption(f"Chunk `{result.get('chunk_id', 'N/A')}` | Similarity {float(score):.4f}")
            preview = str(result.get("content", "")).strip()
            if preview:
                st.write(preview[:320] + ("..." if len(preview) > 320 else ""))


def _render_latest_metadata(
    settings: Settings,
    metadata_manager: MetadataManager,
    last_response: dict[str, object],
) -> None:
    with st.expander("Metadata", expanded=False):
        manifest = _safe_load_manifest(metadata_manager)
        vector_state = _safe_load_vector_state(metadata_manager)
        file_chunk_counts = _count_chunks_by_file(vector_state)
        st.json(
            {
                "provider": settings.app.llm_provider,
                "uploads_path": str(settings.paths.upload_dir),
                "faiss_path": str(settings.paths.faiss_dir),
                "manifest_entries": len(manifest),
                "vector_records": len(vector_state.get("records", []) if vector_state else []),
                "chunk_counts_by_file": dict(file_chunk_counts),
                "document_evidence": last_response.get("document_evidence", []),
            }
        )


def _build_location_caption_from_source(source: dict[str, object]) -> str:
    return _build_location_caption(
        source.get("page_number"),
        source.get("row_number"),
        source.get("chunk_number"),
    )


def _safe_load_manifest(metadata_manager: MetadataManager) -> list[dict[str, object]]:
    try:
        return metadata_manager.load_upload_manifest()
    except ProductSupportAgentError:
        return []


def _safe_load_vector_state(
    metadata_manager: MetadataManager,
) -> dict[str, object] | None:
    try:
        return metadata_manager.load_vector_state()
    except ProductSupportAgentError:
        return None


def _count_chunks_by_file(vector_state: dict[str, object] | None) -> Counter[str]:
    records = vector_state.get("records", []) if vector_state else []
    counter: Counter[str] = Counter()
    for record in records:
        metadata = record.get("metadata") or {}
        file_name = str(metadata.get("file_name", "")).strip()
        if file_name:
            counter[file_name] += 1
    return counter


def _build_location_caption(
    page_number: int | None,
    row_number: int | None,
    chunk_number: int | None,
) -> str:
    parts: list[str] = []
    if page_number is not None:
        parts.append(f"Page {page_number}")
    if row_number is not None:
        parts.append(f"Row {row_number}")
    if chunk_number is not None:
        parts.append(f"Chunk {chunk_number}")
    return " | ".join(parts) or "Chunk reference"
