from __future__ import annotations

from collections import defaultdict
from typing import Any, TypedDict

from product_support_agent.config import Settings
from product_support_agent.exceptions import (
    ConfigurationError,
    GenerationError,
    IndexPersistenceError,
    ProductSupportAgentError,
    ValidationError,
)
from product_support_agent.logger import get_logger
from product_support_agent.models import (
    ConversationMessage,
    DocumentEvidenceSummary,
    RAGResponse,
    RetrievalResult,
    ServiceStatus,
    SourceReference,
)
from product_support_agent.services.gemini_service import GeminiService
from product_support_agent.services.memory import ConversationMemoryService
from product_support_agent.services.prompt_manager import PromptManager
from product_support_agent.services.query_contextualizer import QueryContextualizer
from product_support_agent.services.retriever import RetrieverService


FALLBACK_NO_CONTEXT_MESSAGE = (
    "I could not find enough information in the available knowledge base to answer this question."
)


class RAGGraphState(TypedDict, total=False):
    original_query: str
    resolved_query: str
    conversation_history: list[ConversationMessage]
    memory_messages_used: int
    requested_top_k: int
    retrieval_top_k: int
    retrieved_results: list[RetrievalResult]
    relevant_results: list[RetrievalResult]
    reasoning_strategy: str
    document_evidence: list[DocumentEvidenceSummary]
    generated_answer: str
    citations: list[SourceReference]
    grounded: bool
    message: str
    error: str
    source_documents: list[str]
    graph_nodes_executed: list[str]
    retrieved_chunk_count: int
    relevant_chunk_count: int
    should_stop: bool


class RAGService:
    """Coordinates grounded RAG execution through a LangGraph workflow."""

    def __init__(
        self,
        settings: Settings,
        *,
        retriever_service: RetrieverService | None = None,
        gemini_service: GeminiService | None = None,
        prompt_manager: PromptManager | None = None,
        conversation_memory_service: ConversationMemoryService | None = None,
        query_contextualizer: QueryContextualizer | None = None,
    ) -> None:
        self._settings = settings
        self._logger = get_logger(__name__)
        self._retriever = retriever_service or RetrieverService(settings)
        self._gemini_service = gemini_service or GeminiService(settings)
        self._prompt_manager = prompt_manager or PromptManager(settings)
        self._conversation_memory = conversation_memory_service
        self._query_contextualizer = query_contextualizer or QueryContextualizer(
            settings,
            gemini_service=self._gemini_service,
            prompt_manager=self._prompt_manager,
        )
        self._graph = self._build_graph()

    def answer_question(self, query: str, top_k: int | None = None) -> RAGResponse:
        normalized_query = self._retriever.validate_query(query)
        requested_top_k = self._validate_top_k(top_k)
        retrieval_top_k = requested_top_k + self._settings.app.rag_context_expansion_chunks

        self._logger.info(
            "LangGraph RAG execution started: requested_top_k=%s retrieval_top_k=%s query_length=%s",
            requested_top_k,
            retrieval_top_k,
            len(normalized_query),
        )

        initial_state: RAGGraphState = {
            "original_query": normalized_query,
            "resolved_query": normalized_query,
            "conversation_history": [],
            "memory_messages_used": 0,
            "requested_top_k": requested_top_k,
            "retrieval_top_k": retrieval_top_k,
            "retrieved_results": [],
            "relevant_results": [],
            "reasoning_strategy": "SIMPLE_QA",
            "document_evidence": [],
            "generated_answer": "",
            "citations": [],
            "grounded": False,
            "message": "",
            "error": "",
            "source_documents": [],
            "graph_nodes_executed": [],
            "retrieved_chunk_count": 0,
            "relevant_chunk_count": 0,
            "should_stop": False,
        }

        try:
            final_state = self._graph.invoke(initial_state)
        except ValidationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            self._logger.exception("LangGraph RAG execution failed unexpectedly.")
            fallback_state = self._apply_fallback(
                initial_state,
                message="Grounded answer generation failed unexpectedly.",
                error=str(exc),
            )
            final_state = fallback_state

        response = self._response_from_state(final_state)
        self._logger.info(
            "LangGraph RAG execution completed: grounded=%s strategy=%s retrieved=%s relevant=%s",
            response.grounded,
            response.reasoning_strategy,
            response.retrieved_chunk_count,
            response.relevant_chunk_count,
        )
        return response

    def _build_graph(self) -> Any:
        from langgraph.graph import END, START, StateGraph

        workflow = StateGraph(RAGGraphState)
        workflow.add_node("load_memory", self._node_load_memory)
        workflow.add_node("contextualize_query", self._node_contextualize_query)
        workflow.add_node("retrieve_chunks", self._node_retrieve_chunks)
        workflow.add_node("no_results_fallback", self._node_no_results_fallback)
        workflow.add_node("filter_relevance", self._node_filter_relevance)
        workflow.add_node("low_relevance_fallback", self._node_low_relevance_fallback)
        workflow.add_node(
            "determine_reasoning_strategy",
            self._node_determine_reasoning_strategy,
        )
        workflow.add_node("simple_grounded_answer", self._node_simple_grounded_answer)
        workflow.add_node(
            "summarize_document_evidence",
            self._node_summarize_document_evidence,
        )
        workflow.add_node(
            "synthesize_multi_document_answer",
            self._node_synthesize_multi_document_answer,
        )
        workflow.add_node("format_citations", self._node_format_citations)
        workflow.add_node("update_memory", self._node_update_memory)

        workflow.add_edge(START, "load_memory")
        workflow.add_edge("load_memory", "contextualize_query")
        workflow.add_edge("contextualize_query", "retrieve_chunks")
        workflow.add_conditional_edges(
            "retrieve_chunks",
            self._route_after_retrieval,
            {
                "no_results_fallback": "no_results_fallback",
                "filter_relevance": "filter_relevance",
                "format_citations": "format_citations",
            },
        )
        workflow.add_edge("no_results_fallback", "format_citations")
        workflow.add_conditional_edges(
            "filter_relevance",
            self._route_after_relevance,
            {
                "low_relevance_fallback": "low_relevance_fallback",
                "determine_reasoning_strategy": "determine_reasoning_strategy",
                "format_citations": "format_citations",
            },
        )
        workflow.add_edge("low_relevance_fallback", "format_citations")
        workflow.add_conditional_edges(
            "determine_reasoning_strategy",
            self._route_after_strategy,
            {
                "simple_grounded_answer": "simple_grounded_answer",
                "summarize_document_evidence": "summarize_document_evidence",
            },
        )
        workflow.add_edge("simple_grounded_answer", "format_citations")
        workflow.add_conditional_edges(
            "summarize_document_evidence",
            self._route_after_document_summaries,
            {
                "synthesize_multi_document_answer": "synthesize_multi_document_answer",
                "format_citations": "format_citations",
            },
        )
        workflow.add_edge("synthesize_multi_document_answer", "format_citations")
        workflow.add_edge("format_citations", "update_memory")
        workflow.add_edge("update_memory", END)

        return workflow.compile()

    def _node_load_memory(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "load_memory")
        memory_messages = self._get_recent_memory_messages()
        updated_state["conversation_history"] = memory_messages
        updated_state["memory_messages_used"] = len(memory_messages)
        return updated_state

    def _node_contextualize_query(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "contextualize_query")
        resolved_query = self._resolve_query(
            normalized_query=state["original_query"],
            memory_messages=state.get("conversation_history", []),
        )
        updated_state["resolved_query"] = resolved_query
        return updated_state

    def _node_retrieve_chunks(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "retrieve_chunks")
        try:
            retrieval_response = self._retriever.retrieve(
                query=state["resolved_query"],
                top_k=state["retrieval_top_k"],
            )
        except ValidationError:
            raise
        except IndexPersistenceError as exc:
            self._logger.warning("LangGraph RAG fallback triggered because the FAISS index is unavailable.")
            return self._apply_fallback(
                updated_state,
                message=str(exc),
                error=str(exc),
            )
        except ProductSupportAgentError as exc:
            self._logger.exception("Retrieval failed during LangGraph RAG execution.")
            return self._apply_fallback(
                updated_state,
                message="Retrieval failed while preparing grounded context.",
                error=str(exc),
            )

        retrieved_results = list(retrieval_response.results)
        updated_state["retrieved_results"] = retrieved_results
        updated_state["retrieved_chunk_count"] = len(retrieved_results)
        self._logger.info(
            "LangGraph retrieval node completed: resolved_query=%s raw_results=%s",
            state["resolved_query"],
            len(retrieved_results),
        )
        return updated_state

    def _route_after_retrieval(self, state: RAGGraphState) -> str:
        if state.get("should_stop"):
            return "format_citations"
        if not state.get("retrieved_results"):
            return "no_results_fallback"
        return "filter_relevance"

    def _node_no_results_fallback(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "no_results_fallback")
        return self._apply_fallback(
            updated_state,
            message="No relevant context was retrieved from the knowledge base.",
        )

    def _node_filter_relevance(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "filter_relevance")
        relevant_results = self._filter_relevant_results(state.get("retrieved_results", []))
        updated_state["relevant_results"] = relevant_results
        updated_state["relevant_chunk_count"] = len(relevant_results)
        updated_state["source_documents"] = self._extract_source_documents(relevant_results)
        return updated_state

    def _route_after_relevance(self, state: RAGGraphState) -> str:
        if state.get("should_stop"):
            return "format_citations"
        if not state.get("relevant_results"):
            return "low_relevance_fallback"
        return "determine_reasoning_strategy"

    def _node_low_relevance_fallback(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "low_relevance_fallback")
        return self._apply_fallback(
            updated_state,
            message=(
                "Retrieved chunks did not meet the configured relevance threshold for "
                "grounded answer generation."
            ),
        )

    def _node_determine_reasoning_strategy(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "determine_reasoning_strategy")
        reasoning_strategy = self._determine_reasoning_strategy(
            query=state["original_query"],
            relevant_results=state.get("relevant_results", []),
        )
        updated_state["reasoning_strategy"] = reasoning_strategy
        self._logger.info(
            "LangGraph reasoning strategy selected: strategy=%s documents=%s",
            reasoning_strategy,
            len(updated_state.get("source_documents", [])),
        )
        return updated_state

    def _route_after_strategy(self, state: RAGGraphState) -> str:
        if state.get("reasoning_strategy") == "MULTI_DOCUMENT_REASONING":
            return "summarize_document_evidence"
        return "simple_grounded_answer"

    def _node_simple_grounded_answer(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "simple_grounded_answer")
        relevant_results = state.get("relevant_results", [])
        context = self._build_context(relevant_results)
        if not context.strip():
            return self._apply_fallback(
                updated_state,
                message="Grounded context could not be constructed from the retrieved results.",
            )

        try:
            answer = self._gemini_service.generate_answer(
                system_instruction=self._prompt_manager.load_default_prompt(),
                context=context,
                user_question=state["original_query"],
                resolved_query=state.get("resolved_query"),
            )
        except (ConfigurationError, GenerationError) as exc:
            self._logger.warning("Simple grounded answer generation failed: %s", str(exc))
            return self._apply_generation_unavailable(
                updated_state,
                error=str(exc),
            )

        if not answer.strip():
            return self._apply_fallback(
                updated_state,
                message="Gemini returned an empty grounded answer.",
            )

        updated_state["generated_answer"] = answer
        updated_state["grounded"] = True
        updated_state["message"] = "Grounded answer generated successfully."
        return updated_state

    def _node_summarize_document_evidence(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "summarize_document_evidence")
        grouped_results = self._group_results_by_document(state.get("relevant_results", []))
        if len(grouped_results) <= 1:
            updated_state["reasoning_strategy"] = "SIMPLE_QA"
            return updated_state

        summary_prompt = self._prompt_manager.load_document_summary_prompt()
        evidence_summaries: list[DocumentEvidenceSummary] = []

        self._logger.info(
            "LangGraph multi-document summarization started: documents=%s",
            len(grouped_results),
        )
        for file_name, document_results in grouped_results.items():
            try:
                summary = self._gemini_service.generate_text(
                    system_instruction=summary_prompt,
                    user_content=self._build_document_summary_request(
                        query=state["original_query"],
                        file_name=file_name,
                        results=document_results,
                    ),
                    temperature=self._settings.app.gemini_temperature,
                    max_output_tokens=self._settings.app.gemini_max_output_tokens,
                    task_name="document evidence summarization",
                )
            except (ConfigurationError, GenerationError) as exc:
                self._logger.warning(
                    "Document evidence summarization failed for %s: %s",
                    file_name,
                    str(exc),
                )
                return self._apply_generation_unavailable(
                    updated_state,
                    error=str(exc),
                )

            evidence_summaries.append(
                DocumentEvidenceSummary(
                    file_name=file_name,
                    summary=summary,
                    chunk_ids=[result.chunk_id for result in document_results],
                )
            )

        updated_state["document_evidence"] = evidence_summaries
        return updated_state

    def _route_after_document_summaries(self, state: RAGGraphState) -> str:
        if state.get("should_stop"):
            return "format_citations"
        if state.get("reasoning_strategy") != "MULTI_DOCUMENT_REASONING":
            return "format_citations"
        return "synthesize_multi_document_answer"

    def _node_synthesize_multi_document_answer(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "synthesize_multi_document_answer")
        evidence_summaries = state.get("document_evidence", [])
        if not evidence_summaries:
            return self._apply_fallback(
                updated_state,
                message="Grounded context could not be constructed from the retrieved results.",
            )

        synthesis_prompt = self._prompt_manager.load_multi_document_synthesis_prompt()
        try:
            answer = self._gemini_service.generate_text(
                system_instruction=synthesis_prompt,
                user_content=self._build_multi_document_synthesis_request(
                    query=state["original_query"],
                    evidence_summaries=evidence_summaries,
                ),
                temperature=self._settings.app.gemini_temperature,
                max_output_tokens=self._settings.app.gemini_max_output_tokens,
                task_name="multi-document synthesis",
            )
        except (ConfigurationError, GenerationError) as exc:
            self._logger.warning("Multi-document synthesis failed: %s", str(exc))
            return self._apply_generation_unavailable(
                updated_state,
                error=str(exc),
            )

        if not answer.strip():
            return self._apply_fallback(
                updated_state,
                message="Gemini returned an empty grounded answer.",
            )

        updated_state["generated_answer"] = answer
        updated_state["grounded"] = True
        updated_state["message"] = "Grounded answer generated successfully."
        return updated_state

    def _node_format_citations(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "format_citations")
        citation_results = state.get("relevant_results") or state.get("retrieved_results", [])
        updated_state["citations"] = self._build_sources(citation_results)
        if not updated_state.get("source_documents"):
            updated_state["source_documents"] = self._extract_source_documents(citation_results)
        return updated_state

    def _node_update_memory(self, state: RAGGraphState) -> RAGGraphState:
        updated_state = self._record_node(state, "update_memory")
        response = self._response_from_state(updated_state)
        self._store_conversation_turn(
            user_query=updated_state["original_query"],
            response=response,
        )
        return updated_state

    def _validate_top_k(self, top_k: int | None) -> int:
        requested_top_k = top_k if top_k is not None else self._settings.app.top_k_results
        if requested_top_k <= 0:
            raise ValidationError("Top-K must be greater than zero.")
        return requested_top_k

    def _filter_relevant_results(
        self,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        threshold = self._settings.app.rag_relevance_threshold
        deduplicated_results: list[RetrievalResult] = []
        seen_chunk_ids: set[str] = set()

        for result in results:
            if result.chunk_id in seen_chunk_ids:
                continue
            if result.score < threshold:
                continue
            seen_chunk_ids.add(result.chunk_id)
            deduplicated_results.append(result)

        self._logger.info(
            "LangGraph relevance filtering completed: threshold=%.4f raw_results=%s usable_results=%s",
            threshold,
            len(results),
            len(deduplicated_results),
        )
        return deduplicated_results

    @staticmethod
    def _build_context(results: list[RetrievalResult]) -> str:
        blocks: list[str] = []
        for index, result in enumerate(results, start=1):
            lines = [
                f"[SOURCE {index}]",
                f"File: {result.source_file}",
                f"Document Type: {result.document_type}",
            ]
            if result.page_number is not None:
                lines.append(f"Page: {result.page_number}")
            if result.row_number is not None:
                lines.append(f"Row: {result.row_number}")
            if result.chunk_number is not None:
                lines.append(f"Chunk: {result.chunk_number}")
            lines.extend(
                [
                    f"Chunk ID: {result.chunk_id}",
                    "Content:",
                    result.content,
                ]
            )
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    @staticmethod
    def _build_sources(results: list[RetrievalResult]) -> list[SourceReference]:
        sources: list[SourceReference] = []
        seen_keys: set[tuple[str, int | None, int | None, int | None, str]] = set()
        for result in results:
            key = (
                result.source_file,
                result.page_number,
                result.row_number,
                result.chunk_number,
                result.chunk_id,
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            sources.append(
                SourceReference(
                    file_name=result.source_file,
                    page_number=result.page_number,
                    row_number=result.row_number,
                    chunk_number=result.chunk_number,
                    chunk_id=result.chunk_id,
                )
            )
        return sources

    @staticmethod
    def _extract_source_documents(results: list[RetrievalResult]) -> list[str]:
        seen_files: set[str] = set()
        file_names: list[str] = []
        for result in results:
            if result.source_file in seen_files:
                continue
            seen_files.add(result.source_file)
            file_names.append(result.source_file)
        return file_names

    def _determine_reasoning_strategy(
        self,
        *,
        query: str,
        relevant_results: list[RetrievalResult],
    ) -> str:
        source_documents = self._extract_source_documents(relevant_results)
        if len(source_documents) <= 1:
            return "SIMPLE_QA"

        normalized_query = query.lower()
        multi_document_signals = (
            "compare",
            "comparison",
            "difference",
            "differences",
            "different",
            "similar",
            "similarities",
            "summarize",
            "summary",
            "across",
            "both",
            "versus",
            " vs ",
        )
        if any(signal in normalized_query for signal in multi_document_signals):
            return "MULTI_DOCUMENT_REASONING"
        return "SIMPLE_QA"

    @staticmethod
    def _group_results_by_document(
        results: list[RetrievalResult],
    ) -> dict[str, list[RetrievalResult]]:
        grouped_results: dict[str, list[RetrievalResult]] = defaultdict(list)
        for result in results:
            grouped_results[result.source_file].append(result)
        return dict(grouped_results)

    def _build_document_summary_request(
        self,
        *,
        query: str,
        file_name: str,
        results: list[RetrievalResult],
    ) -> str:
        blocks: list[str] = [f"USER QUESTION:\n{query}", f"DOCUMENT FILE:\n{file_name}"]
        for index, result in enumerate(results, start=1):
            lines = [
                f"[DOCUMENT SOURCE {index}]",
                f"File: {result.source_file}",
                f"Document Type: {result.document_type}",
            ]
            if result.page_number is not None:
                lines.append(f"Page: {result.page_number}")
            if result.row_number is not None:
                lines.append(f"Row: {result.row_number}")
            if result.chunk_number is not None:
                lines.append(f"Chunk: {result.chunk_number}")
            lines.extend(
                [
                    f"Chunk ID: {result.chunk_id}",
                    "Content:",
                    result.content,
                ]
            )
            blocks.append("\n".join(lines))
        blocks.append("EVIDENCE SUMMARY:\n")
        return "\n\n".join(blocks)

    @staticmethod
    def _build_multi_document_synthesis_request(
        *,
        query: str,
        evidence_summaries: list[DocumentEvidenceSummary],
    ) -> str:
        blocks: list[str] = [f"USER QUESTION:\n{query}"]
        for index, evidence in enumerate(evidence_summaries, start=1):
            chunk_ids = ", ".join(evidence.chunk_ids)
            lines = [
                f"[DOCUMENT EVIDENCE {index}]",
                f"File: {evidence.file_name}",
                f"Supporting Chunk IDs: {chunk_ids}",
                "Summary:",
                evidence.summary,
            ]
            blocks.append("\n".join(lines))
        blocks.append("FINAL ANSWER:\n")
        return "\n\n".join(blocks)

    def _apply_fallback(
        self,
        state: RAGGraphState,
        *,
        message: str,
        error: str = "",
    ) -> RAGGraphState:
        updated_state = dict(state)
        updated_state["generated_answer"] = FALLBACK_NO_CONTEXT_MESSAGE
        updated_state["grounded"] = False
        updated_state["message"] = message
        updated_state["error"] = error
        updated_state["should_stop"] = True
        self._logger.info("LangGraph RAG fallback triggered: %s", message)
        return updated_state

    def _apply_generation_unavailable(
        self,
        state: RAGGraphState,
        *,
        error: str,
    ) -> RAGGraphState:
        updated_state = dict(state)
        updated_state["generated_answer"] = ""
        updated_state["grounded"] = False
        updated_state["message"] = "Grounded answer generation is currently unavailable."
        updated_state["error"] = error
        updated_state["should_stop"] = True
        return updated_state

    def _response_from_state(self, state: RAGGraphState) -> RAGResponse:
        response_results = state.get("relevant_results") or state.get("retrieved_results", [])
        return RAGResponse(
            query=state["original_query"],
            answer=state.get("generated_answer", ""),
            sources=state.get("citations", []),
            retrieved_results=list(response_results),
            grounded=state.get("grounded", False),
            reasoning_strategy=state.get("reasoning_strategy", "SIMPLE_QA"),
            graph_nodes_executed=list(state.get("graph_nodes_executed", [])),
            retrieved_chunk_count=state.get("retrieved_chunk_count", 0),
            relevant_chunk_count=state.get("relevant_chunk_count", 0),
            source_documents=list(state.get("source_documents", [])),
            document_evidence=list(state.get("document_evidence", [])),
            resolved_query=state.get("resolved_query"),
            memory_messages_used=state.get("memory_messages_used", 0),
            message=state.get("message", ""),
            error=state.get("error", ""),
        )

    def _get_recent_memory_messages(self) -> list[ConversationMessage]:
        if self._conversation_memory is None:
            return []
        recent_history = self._conversation_memory.get_recent_history()
        self._logger.info("Conversation history loaded: messages=%s", len(recent_history))
        return recent_history

    def _resolve_query(
        self,
        *,
        normalized_query: str,
        memory_messages: list[ConversationMessage],
    ) -> str:
        resolved_query = self._query_contextualizer.resolve_query(
            current_query=normalized_query,
            history=memory_messages,
        )
        self._logger.info(
            "Resolved retrieval query prepared: original_query=%s resolved_query=%s",
            normalized_query,
            resolved_query,
        )
        return resolved_query

    def _store_conversation_turn(self, *, user_query: str, response: RAGResponse) -> None:
        if self._conversation_memory is None:
            return

        self._conversation_memory.add_user_message(user_query)
        if response.answer.strip():
            self._conversation_memory.add_assistant_message(
                response.answer,
                grounded=response.grounded,
            )
        self._logger.info(
            "Conversation memory updated after LangGraph RAG completion: grounded=%s",
            response.grounded,
        )

    @staticmethod
    def _record_node(state: RAGGraphState, node_name: str) -> RAGGraphState:
        updated_state = dict(state)
        updated_state["graph_nodes_executed"] = [
            *state.get("graph_nodes_executed", []),
            node_name,
        ]
        return updated_state

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="rag_service",
            state="ready",
            details=(
                "LangGraph orchestration is active for grounded RAG with relevance threshold "
                f"{self._settings.app.rag_relevance_threshold}, context expansion "
                f"{self._settings.app.rag_context_expansion_chunks}, and memory-aware retrieval."
            ),
        )
