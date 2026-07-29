from __future__ import annotations

from collections import Counter
from datetime import datetime
from time import perf_counter

import streamlit as st

from product_support_agent.config import Settings
from product_support_agent.exceptions import ProductSupportAgentError
from product_support_agent.models import UploadPayload
from product_support_agent.services.indexing_pipeline import KnowledgeBaseIngestionPipeline
from product_support_agent.services.knowledge_base_service import KnowledgeBaseService
from product_support_agent.services.memory import ConversationMemoryService
from product_support_agent.services.metadata_manager import MetadataManager
from product_support_agent.services.rag_service import RAGService
from product_support_agent.services.upload_manager import UploadManager
from product_support_agent.ui.presenter import (
    LAST_RAG_RESPONSE_KEY,
    append_chat_record,
    clear_chat_transcript,
    consume_clear_conversation_request,
    get_chat_transcript,
    get_search_depth,
)
from product_support_agent.ui.theme import (
    build_simple_card,
    render_card_grid,
    render_conversation_turn,
    render_message_bubble,
)
from product_support_agent.utils import human_readable_size


_CHAT_SESSION_ID = "ask_knowledge_base"
_CLEAR_KB_SUCCESS_KEY = "ui_clear_knowledge_base_success"
_UPLOAD_WIDGET_VERSION_KEY = "ui_upload_widget_version"


def _load_upload_manifest(settings: Settings) -> list[dict[str, object]]:
    metadata_manager = MetadataManager(settings)
    try:
        return metadata_manager.load_upload_manifest()
    except ProductSupportAgentError:
        return []


def render_upload_section(settings: Settings) -> None:
    success_message = st.session_state.pop(_CLEAR_KB_SUCCESS_KEY, "")
    if success_message:
        st.success(success_message)

    st.subheader("Add Knowledge")
    st.caption(
        "Upload your documents once so the assistant can search them and answer with grounded references."
    )

    upload_manager = UploadManager(settings)
    pipeline = KnowledgeBaseIngestionPipeline(settings)
    uploader_version = int(st.session_state.get(_UPLOAD_WIDGET_VERSION_KEY, 0))
    uploaded_files = st.file_uploader(
        "Choose files",
        type=[extension.lstrip(".") for extension in upload_manager.supported_extensions()],
        accept_multiple_files=True,
        key=f"knowledge-base-upload-{uploader_version}",
        help=(
            f"Supported types: {', '.join(upload_manager.supported_extensions())}. "
            f"Maximum file size: {settings.app.max_upload_size_mb} MB."
        ),
    )

    if uploaded_files:
        st.markdown("### Ready to Add")
        render_card_grid(
            [
                build_simple_card(
                    title=f"{_pending_file_icon(uploaded_file.name)} {uploaded_file.name}",
                    value=human_readable_size(uploaded_file.size),
                    caption="Ready to process",
                )
                for uploaded_file in uploaded_files
            ]
        )

    action_col, clear_col = st.columns([1.3, 1], vertical_alignment="center")
    with action_col:
        build_requested = st.button("Build Knowledge Base", type="primary")
    with clear_col:
        clear_requested = st.button("🗑 Clear Knowledge Base", type="secondary")

    if clear_requested:
        knowledge_base_service = KnowledgeBaseService(settings)
        conversation_memory = ConversationMemoryService(
            settings,
            storage=st.session_state,
            session_id=_CHAT_SESSION_ID,
        )
        knowledge_base_service.clear()
        conversation_memory.clear_history()
        clear_chat_transcript()
        st.session_state.pop(LAST_RAG_RESPONSE_KEY, None)
        st.session_state[_UPLOAD_WIDGET_VERSION_KEY] = uploader_version + 1
        st.session_state[_CLEAR_KB_SUCCESS_KEY] = (
            "Knowledge base cleared successfully. Upload new documents to begin indexing."
        )
        st.rerun()

    if build_requested:
        if not uploaded_files:
            st.warning("Choose at least one file before updating the knowledge base.")
        else:
            payloads = [
                UploadPayload(
                    file_name=uploaded_file.name,
                    content=uploaded_file.getvalue(),
                )
                for uploaded_file in uploaded_files
            ]
            progress = st.progress(5)
            stage = st.empty()
            stage.caption("Checking your files...")
            try:
                progress.progress(35)
                stage.caption("Adding documents to the knowledge base...")
                result = pipeline.ingest_uploads(payloads)
            except ProductSupportAgentError as exc:
                progress.empty()
                stage.empty()
                st.error(str(exc))
            else:
                progress.progress(100)
                stage.caption("Knowledge base update complete.")
                for duplicate_message in result.duplicate_messages:
                    st.info(duplicate_message)
                st.success("Your knowledge base is ready.")
                render_card_grid(
                    [
                        build_simple_card(
                            title="Uploaded Files",
                            value=str(result.uploaded_files),
                            caption="Added in this update",
                        ),
                        build_simple_card(
                            title="Extracted Documents",
                            value=str(result.extracted_documents),
                            caption="Read successfully",
                        ),
                        build_simple_card(
                            title="Chunks Created",
                            value=str(result.chunks_created),
                            caption="Prepared for search",
                        ),
                        build_simple_card(
                            title="Vectors in Index",
                            value=str(result.vectors_in_index),
                            caption="Stored in the knowledge base",
                        ),
                    ],
                    css_class="psa-source-grid",
                )

    manifest = _load_upload_manifest(settings)
    if manifest:
        st.markdown("### Knowledge Base")
        chunk_counts = _load_chunk_counts_by_file(settings)
        render_card_grid(
            [
                build_simple_card(
                    title=f"{_document_icon(item)} {str(item.get('stored_file_name', 'Unknown'))}",
                    value=human_readable_size(int(item.get("file_size_bytes", 0))),
                    caption=(
                        f"Indexed | {chunk_counts.get(str(item.get('stored_file_name', '')), 0)} chunks"
                    ),
                )
                for item in manifest
            ]
        )


def render_rag_section(settings: Settings) -> None:
    conversation_memory = ConversationMemoryService(
        settings,
        storage=st.session_state,
        session_id=_CHAT_SESSION_ID,
    )
    rag_service = RAGService(
        settings,
        conversation_memory_service=conversation_memory,
    )

    if consume_clear_conversation_request():
        conversation_memory.clear_history()
        clear_chat_transcript()
        st.session_state.pop(LAST_RAG_RESPONSE_KEY, None)
        st.rerun()

    search_depth = get_search_depth(settings)
    history = conversation_memory.get_history()
    transcript = get_chat_transcript()

    with st.container(border=True):
        if not transcript and not history:
            st.info(
                "Ask a question about your uploaded documents. The assistant will answer using the knowledge base."
            )
        else:
            _render_chat_thread(transcript=transcript, fallback_history=history)

    with st.form("ask_ai_form", clear_on_submit=True, border=False):
        prompt = st.text_area(
            "Ask AI",
            placeholder="Ask anything about your uploaded documentation...",
            label_visibility="collapsed",
            height=128,
        )
        action_col, _ = st.columns([1.25, 6], vertical_alignment="bottom")
        with action_col:
            submitted = st.form_submit_button(
                "Send",
                type="primary",
                use_container_width=True,
            )

    if submitted and prompt:
        timestamp = _format_ui_timestamp()
        append_chat_record({"role": "user", "content": prompt, "timestamp": timestamp})
        start_time = perf_counter()
        try:
            with st.spinner("Thinking..."):
                response = rag_service.answer_question(query=prompt, top_k=search_depth)
        except ProductSupportAgentError as exc:
            elapsed_ms = round((perf_counter() - start_time) * 1000, 2)
            error_payload = {
                "query": prompt,
                "answer": "",
                "sources": [],
                "retrieved_results": [],
                "selected_results": [],
                "grounded": False,
                "reasoning_strategy": "SIMPLE_QA",
                "graph_nodes_executed": [],
                "retrieved_chunk_count": 0,
                "relevant_chunk_count": 0,
                "source_documents": [],
                "document_evidence": [],
                "resolved_query": prompt,
                "memory_messages_used": len(history),
                "message": "The assistant could not complete the request.",
                "error": str(exc),
                "response_time_ms": elapsed_ms,
            }
            st.session_state[LAST_RAG_RESPONSE_KEY] = error_payload
            append_chat_record(
                {
                    "role": "assistant",
                    "content": str(exc),
                    "grounded": False,
                    "timestamp": _format_ui_timestamp(),
                    "response": error_payload,
                }
            )
        else:
            elapsed_ms = round((perf_counter() - start_time) * 1000, 2)
            latest_response = response.to_dict()
            latest_response["response_time_ms"] = elapsed_ms
            st.session_state[LAST_RAG_RESPONSE_KEY] = latest_response
            append_chat_record(
                {
                    "role": "assistant",
                    "content": response.answer or response.message or "No answer was generated.",
                    "grounded": response.grounded,
                    "timestamp": _format_ui_timestamp(),
                    "response": latest_response,
                }
            )
        st.rerun()


def _render_chat_thread(
    *,
    transcript: list[dict[str, object]],
    fallback_history: list[object],
) -> None:
    if transcript:
        turns = _build_transcript_turns(transcript)
        for turn in turns:
            if turn["user_content"]:
                render_conversation_turn(
                    user_content=turn["user_content"],
                    assistant_content=turn["assistant_content"] or None,
                    user_timestamp=turn["user_timestamp"],
                    assistant_timestamp=turn["assistant_timestamp"],
                )
            elif turn["assistant_content"]:
                render_message_bubble(
                    role="assistant",
                    content=turn["assistant_content"],
                    timestamp=turn["assistant_timestamp"],
                )
        return

    turns = _build_history_turns(fallback_history)
    for turn in turns:
        if turn["user_content"]:
            render_conversation_turn(
                user_content=turn["user_content"],
                assistant_content=turn["assistant_content"] or None,
                user_timestamp=turn["user_timestamp"],
                assistant_timestamp=turn["assistant_timestamp"],
            )
        elif turn["assistant_content"]:
            render_message_bubble(
                role="assistant",
                content=turn["assistant_content"],
                timestamp=turn["assistant_timestamp"],
            )


def _render_response_details(response: dict[str, object], *, key_prefix: str) -> None:
    sources = response.get("sources", [])
    retrieved_results = response.get("retrieved_results", [])

    with st.expander(f"Sources ({len(sources)})", expanded=False):
        if not sources:
            st.info("No source citations are available for this answer.")
        else:
            _render_source_cards(response=response)

    with st.expander("Debug", expanded=False):
        _render_debug_contents(
            latest_response=response,
            key_prefix=f"{key_prefix}-debug",
        )
        if retrieved_results:
            st.markdown("### Retrieved Context")
            _render_retrieved_results(
                [dict(item) for item in retrieved_results if isinstance(item, dict)],
                key_prefix=f"{key_prefix}-retrieved",
            )
        else:
            st.info("No retrieved chunks were available for inspection.")


def _render_source_cards(response: dict[str, object]) -> None:
    sources = response.get("sources", [])
    retrieved_results = response.get("retrieved_results", [])
    results_by_chunk = {
        str(item.get("chunk_id", "")): item
        for item in retrieved_results
        if isinstance(item, dict)
    }

    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue
        chunk_id = str(source.get("chunk_id", ""))
        result = results_by_chunk.get(chunk_id, {})
        with st.container(border=True):
            cols = st.columns([3, 1.2, 1.1])
            with cols[0]:
                st.markdown(f"**Source {index}**")
                st.write(str(source.get("file_name", "Unknown file")))
            with cols[1]:
                st.markdown("**Location**")
                st.write(_format_source_location(source))
            with cols[2]:
                st.markdown("**Similarity**")
                if result.get("score") is None:
                    st.write("N/A")
                else:
                    st.write(f"{float(result['score']):.4f}")

            with st.expander("Preview", expanded=False):
                preview = str(result.get("content", "")).strip()
                if preview:
                    st.write(preview)
                else:
                    st.info("No chunk preview is available for this source.")


def _render_debug_contents(latest_response: dict[str, object], *, key_prefix: str) -> None:
    st.markdown(f"**Original Query:** `{latest_response.get('query', '')}`")
    st.markdown(
        f"**Resolved Retrieval Query:** `{latest_response.get('resolved_query', '')}`"
    )
    st.markdown(
        f"**Memory Messages Used:** `{latest_response.get('memory_messages_used', 0)}`"
    )
    st.markdown(
        f"**Reasoning Strategy:** `{latest_response.get('reasoning_strategy', 'SIMPLE_QA')}`"
    )
    st.markdown(
        f"**Graph Nodes Executed:** `{', '.join(latest_response.get('graph_nodes_executed', []))}`"
    )
    st.markdown(
        f"**Retrieved Chunk Count:** `{latest_response.get('retrieved_chunk_count', 0)}`"
    )
    st.markdown(
        f"**Relevant Chunk Count:** `{latest_response.get('relevant_chunk_count', 0)}`"
    )
    st.markdown(
        f"**Source Documents:** `{', '.join(latest_response.get('source_documents', []))}`"
    )
    response_time = latest_response.get("response_time_ms")
    if response_time is not None:
        st.markdown(f"**Response Time:** `{response_time} ms`")

    message = str(latest_response.get("message", "")).strip()
    error = str(latest_response.get("error", "")).strip()
    if message:
        st.markdown(f"**Message:** `{message}`")
    if error:
        st.markdown(f"**Error:** `{error}`")

    document_evidence = latest_response.get("document_evidence", [])
    if document_evidence:
        st.markdown("### Document Evidence Summaries")
        for evidence in document_evidence:
            if not isinstance(evidence, dict):
                continue
            with st.container(border=True):
                st.markdown(f"**File:** `{evidence.get('file_name', '')}`")
                st.markdown(
                    f"**Chunk IDs:** `{', '.join(evidence.get('chunk_ids', []))}`"
                )
                st.text_area(
                    "Evidence Summary",
                    value=evidence.get("summary", ""),
                    height=140,
                    disabled=True,
                    key=f"{key_prefix}-evidence-{evidence.get('file_name', '')}",
                )


def _render_retrieved_results(
    retrieved_results: list[dict[str, object]],
    *,
    key_prefix: str,
) -> None:
    for index, result in enumerate(retrieved_results, start=1):
        with st.container(border=True):
            cols = st.columns([3, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**Result {index}**")
                st.write(str(result.get("source_file", "Unknown file")))
            with cols[1]:
                st.markdown("**Chunk**")
                st.write(str(result.get("chunk_id", "N/A")))
            with cols[2]:
                st.markdown("**Type**")
                st.write(str(result.get("document_type", "unknown")).upper())
            with cols[3]:
                st.markdown("**Similarity**")
                score = result.get("score")
                st.write(f"{float(score):.4f}" if score is not None else "N/A")

            location = _format_result_location(result)
            if location:
                st.caption(location)

            with st.expander("Chunk Preview", expanded=False):
                st.text_area(
                    "Retrieved Chunk",
                    value=str(result.get("content", "")),
                    height=180,
                    disabled=True,
                    key=f"{key_prefix}-{result.get('chunk_id', index)}",
                )


def _format_result_location(result: dict[str, object]) -> str:
    parts: list[str] = []
    if result.get("page_number") is not None:
        parts.append(f"Page {result['page_number']}")
    if result.get("row_number") is not None:
        parts.append(f"Row {result['row_number']}")
    if result.get("chunk_number") is not None:
        parts.append(f"Chunk {result['chunk_number']}")
    return " | ".join(parts)


def _format_source_location(source: dict[str, object]) -> str:
    parts: list[str] = []
    if source.get("page_number") is not None:
        parts.append(f"Page {source['page_number']}")
    if source.get("row_number") is not None:
        parts.append(f"Row {source['row_number']}")
    if source.get("chunk_number") is not None:
        parts.append(f"Chunk {source['chunk_number']}")
    return " | ".join(parts) or "Chunk reference"


def _load_chunk_counts_by_file(settings: Settings) -> Counter[str]:
    metadata_manager = MetadataManager(settings)
    try:
        vector_state = metadata_manager.load_vector_state()
    except ProductSupportAgentError:
        return Counter()

    records = vector_state.get("records", []) if vector_state else []
    counter: Counter[str] = Counter()
    for record in records:
        metadata = record.get("metadata") or {}
        file_name = str(metadata.get("file_name", "")).strip()
        if file_name:
            counter[file_name] += 1
    return counter


def _document_icon(item: dict[str, object]) -> str:
    document_type = str((item.get("document_metadata") or {}).get("document_type", "")).lower()
    return {
        "pdf": "\U0001F4D5",
        "txt": "\U0001F4DD",
        "csv": "\U0001F9FE",
    }.get(document_type, "\U0001F4C4")


def _pending_file_icon(file_name: str) -> str:
    lower_name = file_name.lower()
    if lower_name.endswith(".pdf"):
        return "\U0001F4D5"
    if lower_name.endswith(".txt"):
        return "\U0001F4DD"
    if lower_name.endswith(".csv"):
        return "\U0001F9FE"
    return "\U0001F4C4"


def _format_ui_timestamp() -> str:
    return datetime.now().strftime("%I:%M %p").lstrip("0")


def _coerce_message_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%I:%M %p").lstrip("0")
    return ""


def _build_transcript_turns(
    transcript: list[dict[str, object]],
) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    current_turn: dict[str, str] | None = None

    for record in transcript:
        role = str(record.get("role", "assistant"))
        content = str(record.get("content", ""))
        timestamp = str(record.get("timestamp", ""))

        if role == "user":
            current_turn = {
                "user_content": content,
                "user_timestamp": timestamp,
                "assistant_content": "",
                "assistant_timestamp": "",
            }
            turns.append(current_turn)
            continue

        if current_turn is None or current_turn.get("assistant_content"):
            current_turn = {
                "user_content": "",
                "user_timestamp": "",
                "assistant_content": content,
                "assistant_timestamp": timestamp,
            }
            turns.append(current_turn)
            continue

        current_turn["assistant_content"] = content
        current_turn["assistant_timestamp"] = timestamp

    return turns


def _build_history_turns(
    fallback_history: list[object],
) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    current_turn: dict[str, str] | None = None

    for message in fallback_history:
        role = getattr(message, "role", "assistant")
        content = getattr(message, "content", "")
        timestamp = _coerce_message_timestamp(getattr(message, "created_at", None))

        if role == "user":
            current_turn = {
                "user_content": content,
                "user_timestamp": timestamp,
                "assistant_content": "",
                "assistant_timestamp": "",
            }
            turns.append(current_turn)
            continue

        if current_turn is None or current_turn.get("assistant_content"):
            current_turn = {
                "user_content": "",
                "user_timestamp": "",
                "assistant_content": content,
                "assistant_timestamp": timestamp,
            }
            turns.append(current_turn)
            continue

        current_turn["assistant_content"] = content
        current_turn["assistant_timestamp"] = timestamp

    return turns
