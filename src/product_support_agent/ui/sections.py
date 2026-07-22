from __future__ import annotations

import streamlit as st

from product_support_agent.config import Settings
from product_support_agent.exceptions import ProductSupportAgentError
from product_support_agent.models import UploadPayload
from product_support_agent.services.indexing_pipeline import KnowledgeBaseIngestionPipeline
from product_support_agent.services.memory import ConversationMemoryService
from product_support_agent.services.metadata_manager import MetadataManager
from product_support_agent.services.rag_service import RAGService
from product_support_agent.services.retriever import RetrieverService
from product_support_agent.services.upload_manager import UploadManager
from product_support_agent.utils import human_readable_size, utc_timestamp


_CHAT_SESSION_ID = "ask_knowledge_base"
_LAST_RAG_RESPONSE_KEY = "last_rag_response"


def _load_upload_manifest(settings: Settings) -> list[dict[str, object]]:
    metadata_manager = MetadataManager(settings)
    try:
        return metadata_manager.load_upload_manifest()
    except ProductSupportAgentError:
        return []


def render_upload_section(settings: Settings) -> None:
    st.subheader("Document Ingestion and Indexing")
    st.write(
        "Upload PDF, TXT, and CSV files, validate them, extract text, chunk content, "
        "generate local embeddings, and persist the knowledge base into FAISS."
    )

    upload_manager = UploadManager(settings)
    pipeline = KnowledgeBaseIngestionPipeline(settings)
    uploaded_files = st.file_uploader(
        "Select source files",
        type=[extension.lstrip(".") for extension in upload_manager.supported_extensions()],
        accept_multiple_files=True,
        help=(
            f"Supported types: {', '.join(upload_manager.supported_extensions())}. "
            f"Maximum file size: {settings.app.max_upload_size_mb} MB."
        ),
    )

    if uploaded_files:
        st.markdown("### Pending Uploads")
        for uploaded_file in uploaded_files:
            st.write(
                f"- `{uploaded_file.name}` ({human_readable_size(uploaded_file.size)})"
            )

    if st.button("Build Knowledge Base", type="primary"):
        if not uploaded_files:
            st.warning("Select at least one file before building the knowledge base.")
        else:
            payloads = [
                UploadPayload(
                    file_name=uploaded_file.name,
                    content=uploaded_file.getvalue(),
                )
                for uploaded_file in uploaded_files
            ]
            try:
                result = pipeline.ingest_uploads(payloads)
            except ProductSupportAgentError as exc:
                st.error(str(exc))
            else:
                for duplicate_message in result.duplicate_messages:
                    st.info(duplicate_message)
                st.success("Knowledge base created successfully.")
                st.json(result.to_dict())

    manifest = _load_upload_manifest(settings)
    if manifest:
        st.markdown("### Uploaded File Manifest")
        st.dataframe(
            [
                {
                    "file_name": item["stored_file_name"],
                    "document_type": item["document_metadata"]["document_type"],
                    "file_size_bytes": item["file_size_bytes"],
                    "stored_path": item["stored_path"],
                    "checksum": item["document_metadata"]["checksum"],
                }
                for item in manifest
            ],
            use_container_width=True,
        )


def render_logs_section(settings: Settings) -> None:
    st.subheader("Logs")
    st.info(
        "Application logging is enabled for upload, parsing, chunking, embeddings, "
        "FAISS persistence, retrieval, grounded generation, and errors."
    )
    st.code(
        "\n".join(
            [
                f"timestamp={utc_timestamp()}",
                f"log_file={settings.logging.log_file}",
                f"log_level={settings.logging.level}",
                f"upload_manifest={settings.paths.upload_manifest_file}",
                f"index_file={settings.paths.vector_index_file}",
                f"metadata_file={settings.paths.vector_metadata_file}",
                f"top_k_results={settings.app.top_k_results}",
                f"max_query_length={settings.app.max_query_length}",
                f"gemini_model={settings.app.gemini_model}",
                f"contextualizer_temperature={settings.app.contextualizer_temperature}",
                f"contextualizer_max_output_tokens={settings.app.contextualizer_max_output_tokens}",
                f"rag_relevance_threshold={settings.app.rag_relevance_threshold}",
                f"rag_context_expansion_chunks={settings.app.rag_context_expansion_chunks}",
                f"memory_max_turns={settings.app.memory_max_turns}",
                "status=phase7_langgraph_reasoning_ready",
            ]
        ),
        language="text",
    )


def render_retrieval_section(settings: Settings) -> None:
    st.subheader("Retrieved Context")
    st.write(
        "Use this temporary retrieval section to validate FAISS search quality against "
        "the existing persistent knowledge base. No AI answer generation is performed here."
    )

    retriever = RetrieverService(settings)
    query = st.text_input(
        "User Query",
        placeholder="Enter a question related to the indexed documents...",
    )
    top_k = st.number_input(
        "Top-K Results",
        min_value=1,
        max_value=20,
        value=settings.app.top_k_results,
        step=1,
    )

    if st.button("Retrieve Context", type="primary"):
        try:
            response = retriever.retrieve(query=query, top_k=int(top_k))
        except ProductSupportAgentError as exc:
            st.error(str(exc))
        else:
            if not response.results:
                st.warning("No retrieved context was returned from the FAISS index.")
            else:
                st.success(f"Retrieved {len(response.results)} chunk(s).")
                for result in response.results:
                    with st.container(border=True):
                        st.markdown(f"**Source File:** `{result.source_file}`")
                        st.markdown(f"**Chunk ID:** `{result.chunk_id}`")
                        st.markdown(f"**Document Type:** `{result.document_type}`")
                        st.markdown(f"**Similarity Score:** `{result.score:.6f}`")
                        if result.page_number is not None:
                            st.markdown(f"**Page Number:** `{result.page_number}`")
                        if result.row_number is not None:
                            st.markdown(f"**Row Number:** `{result.row_number}`")
                        if result.chunk_number is not None:
                            st.markdown(f"**Chunk Number:** `{result.chunk_number}`")
                        st.markdown(f"**Source Path:** `{result.source_path}`")
                        st.text_area(
                            "Retrieved Chunk",
                            value=result.content,
                            height=180,
                            disabled=True,
                            key=f"retrieved-{result.chunk_id}",
                        )


def render_rag_section(settings: Settings) -> None:
    st.subheader("Ask Knowledge Base")
    st.write(
        "Ask grounded questions against the persistent FAISS knowledge base, including "
        "follow-up questions that rely on recent conversation context and multi-document reasoning."
    )

    conversation_memory = ConversationMemoryService(
        settings,
        storage=st.session_state,
        session_id=_CHAT_SESSION_ID,
    )
    rag_service = RAGService(
        settings,
        conversation_memory_service=conversation_memory,
    )

    controls_col, clear_col = st.columns([4, 1])
    with controls_col:
        top_k = st.number_input(
            "Top-K Retrieval Depth",
            min_value=1,
            max_value=20,
            value=settings.app.top_k_results,
            step=1,
            help=(
                "The system may retrieve a few extra chunks internally to reduce chunk-boundary "
                "misses before building the grounded context."
            ),
        )
    with clear_col:
        st.write("")
        st.write("")
        if st.button("Clear Conversation", type="secondary", use_container_width=True):
            conversation_memory.clear_history()
            st.session_state.pop(_LAST_RAG_RESPONSE_KEY, None)
            st.rerun()

    history = conversation_memory.get_history()
    if not history:
        st.info("Conversation memory is empty. Ask a grounded question to start the chat.")
    else:
        for index, message in enumerate(history):
            with st.chat_message(message.role):
                st.write(message.content)
                if message.role == "assistant" and message.grounded is False:
                    st.caption("Ungrounded fallback response")

    prompt = st.chat_input("Ask a grounded question or follow-up question...")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)

        try:
            response = rag_service.answer_question(query=prompt, top_k=int(top_k))
        except ProductSupportAgentError as exc:
            st.error(str(exc))
        else:
            st.session_state[_LAST_RAG_RESPONSE_KEY] = response.to_dict()
            with st.chat_message("assistant"):
                if response.error:
                    st.error(response.error)
                elif response.message and not response.grounded:
                    st.warning(response.message)
                st.write(response.answer or "No answer was generated.")

    _render_latest_response_debug()


def render_pipeline_notes_section(settings: Settings) -> None:
    st.subheader("Phase 7 Scope")
    st.write(
        "This phase adds LangGraph orchestration and multi-document reasoning on top of the "
        "existing grounded retrieval, memory, and Gemini generation pipeline."
    )
    st.markdown(
        "\n".join(
            [
                "1. Load recent grounded conversation memory for contextual follow-up handling.",
                "2. Rewrite ambiguous follow-up questions into standalone retrieval queries.",
                "3. Retrieve from the persistent FAISS index using the resolved query.",
                "4. Filter weak results using the configured grounded relevance threshold.",
                "5. Route between simple grounded QA and multi-document reasoning with LangGraph.",
                "6. Summarize per-document evidence and synthesize a grounded final answer when needed.",
                "7. Preserve deterministic citations and update session memory after completion.",
            ]
        )
    )


def _render_latest_response_debug() -> None:
    latest_response = st.session_state.get(_LAST_RAG_RESPONSE_KEY)
    if not latest_response:
        return

    with st.expander("Sources", expanded=False):
        sources = latest_response.get("sources", [])
        if not sources:
            st.info("No source citations are available for the latest response.")
        else:
            for index, source in enumerate(sources, start=1):
                with st.container(border=True):
                    st.markdown(f"**Source {index}:** `{source.get('file_name', '')}`")
                    st.markdown(f"**Chunk ID:** `{source.get('chunk_id', '')}`")
                    if source.get("page_number") is not None:
                        st.markdown(f"**Page Number:** `{source['page_number']}`")
                    if source.get("row_number") is not None:
                        st.markdown(f"**Row Number:** `{source['row_number']}`")
                    if source.get("chunk_number") is not None:
                        st.markdown(f"**Chunk Number:** `{source['chunk_number']}`")

    with st.expander("Debug", expanded=False):
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

        document_evidence = latest_response.get("document_evidence", [])
        if document_evidence:
            st.markdown("**Document Evidence Summaries**")
            for evidence in document_evidence:
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
                        key=f"evidence-{evidence.get('file_name', '')}",
                    )

        retrieved_results = latest_response.get("retrieved_results", [])
        if not retrieved_results:
            st.info("No retrieved chunks were available for inspection.")
        else:
            for result in retrieved_results:
                with st.container(border=True):
                    st.markdown(f"**Source File:** `{result.get('source_file', '')}`")
                    st.markdown(f"**Chunk ID:** `{result.get('chunk_id', '')}`")
                    st.markdown(f"**Document Type:** `{result.get('document_type', '')}`")
                    st.markdown(f"**Similarity Score:** `{result.get('score', 0.0):.6f}`")
                    if result.get("page_number") is not None:
                        st.markdown(f"**Page Number:** `{result['page_number']}`")
                    if result.get("row_number") is not None:
                        st.markdown(f"**Row Number:** `{result['row_number']}`")
                    if result.get("chunk_number") is not None:
                        st.markdown(f"**Chunk Number:** `{result['chunk_number']}`")
                    st.text_area(
                        "Retrieved Chunk",
                        value=result.get("content", ""),
                        height=180,
                        disabled=True,
                        key=f"rag-retrieved-{result.get('chunk_id', '')}",
                    )
