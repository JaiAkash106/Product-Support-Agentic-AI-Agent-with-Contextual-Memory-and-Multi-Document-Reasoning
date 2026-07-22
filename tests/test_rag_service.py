from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from product_support_agent.exceptions import GenerationError, ValidationError
from product_support_agent.models import (
    ConversationMessage,
    RAGResponse,
    RetrievalResponse,
    RetrievalResult,
)
from product_support_agent.services.memory import ConversationMemoryService
from product_support_agent.services.query_contextualizer import QueryContextualizer
from product_support_agent.services.rag_service import (
    FALLBACK_NO_CONTEXT_MESSAGE,
    RAGService,
)


class _FakeRetriever:
    def __init__(
        self,
        *,
        response: RetrievalResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self._response = response
        self._error = error
        self.calls: list[tuple[str, int]] = []

    def validate_query(self, query: str) -> str:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise ValidationError("Query cannot be empty or whitespace only.")
        return normalized_query

    def retrieve(self, query: str, top_k: int) -> RetrievalResponse:
        self.calls.append((query, top_k))
        if self._error is not None:
            raise self._error
        if self._response is None:  # pragma: no cover - defensive guard
            raise AssertionError("A fake retrieval response was not provided.")
        return self._response


class _FakeGeminiService:
    def __init__(
        self,
        *,
        answer: str = "",
        rewrite_answer: str = "",
        task_responses: dict[str, str | list[str]] | None = None,
        error: Exception | None = None,
        rewrite_error: Exception | None = None,
        task_errors: dict[str, Exception] | None = None,
    ) -> None:
        self._answer = answer
        self._rewrite_answer = rewrite_answer
        self._task_responses = dict(task_responses or {})
        self._error = error
        self._rewrite_error = rewrite_error
        self._task_errors = dict(task_errors or {})
        self.calls: list[dict[str, str]] = []
        self.task_calls: list[dict[str, object]] = []

    def generate_answer(
        self,
        *,
        system_instruction: str,
        context: str,
        user_question: str,
        resolved_query: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "context": context,
                "user_question": user_question,
                "resolved_query": resolved_query or "",
            }
        )
        if self._error is not None:
            raise self._error
        return self._answer

    def generate_text(
        self,
        *,
        system_instruction: str,
        user_content: str,
        temperature: float,
        max_output_tokens: int,
        task_name: str,
    ) -> str:
        self.task_calls.append(
            {
                "system_instruction": system_instruction,
                "user_content": user_content,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "task_name": task_name,
            }
        )
        if task_name == "query contextualization" and self._rewrite_error is not None:
            raise self._rewrite_error
        if task_name in self._task_errors:
            raise self._task_errors[task_name]
        if task_name == "query contextualization":
            return self._rewrite_answer

        configured_response = self._task_responses.get(task_name)
        if isinstance(configured_response, list):
            if not configured_response:  # pragma: no cover - defensive guard
                raise AssertionError(f"No fake responses remain for task {task_name}.")
            return configured_response.pop(0)
        if isinstance(configured_response, str):
            return configured_response
        return ""


class _FakeContextualizer:
    def __init__(self, resolved_query: str) -> None:
        self._resolved_query = resolved_query
        self.calls: list[dict[str, object]] = []

    def resolve_query(
        self,
        *,
        current_query: str,
        history: list[ConversationMessage],
    ) -> str:
        self.calls.append(
            {
                "current_query": current_query,
                "history": history,
            }
        )
        return self._resolved_query


def _make_result(
    *,
    chunk_id: str,
    content: str,
    score: float,
    file_name: str = "manual.pdf",
    page_number: int | None = 2,
    chunk_number: int | None = 1,
) -> RetrievalResult:
    return RetrievalResult(
        content=content,
        score=score,
        source_file=file_name,
        source_path=Path("data/uploads") / file_name,
        page_number=page_number,
        row_number=None,
        chunk_number=chunk_number,
        chunk_id=chunk_id,
        document_type="pdf",
    )


def _make_response(query: str, results: list[RetrievalResult]) -> RetrievalResponse:
    return RetrievalResponse(
        query=query,
        top_k=4,
        results=results,
    )


def test_rag_service_generates_grounded_answer_with_sources(test_settings) -> None:
    query = "What are the programming languages supported in the coding session?"
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="manual.pdf:2:na:1",
                    content="The supported programming languages are Java and Python.",
                    score=0.82,
                    chunk_number=1,
                ),
                _make_result(
                    chunk_id="manual.pdf:3:na:2",
                    content="C++ is also supported in the coding session.",
                    score=0.77,
                    page_number=3,
                    chunk_number=2,
                ),
            ],
        )
    )
    gemini = _FakeGeminiService(answer="The supported languages are Java, Python, and C++.")
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=2)

    assert response.grounded is True
    assert response.answer == "The supported languages are Java, Python, and C++."
    assert response.reasoning_strategy == "SIMPLE_QA"
    assert len(response.sources) == 2
    assert response.sources[0].file_name == "manual.pdf"
    assert response.sources[0].page_number == 2
    assert response.retrieved_chunk_count == 2
    assert response.relevant_chunk_count == 2
    assert response.graph_nodes_executed == [
        "load_memory",
        "contextualize_query",
        "retrieve_chunks",
        "filter_relevance",
        "determine_reasoning_strategy",
        "simple_grounded_answer",
        "format_citations",
        "update_memory",
    ]
    assert retriever.calls == [(query, 4)]
    assert "SOURCE 1" in gemini.calls[0]["context"]
    assert "data/uploads" not in gemini.calls[0]["context"]


def test_rag_service_deduplicates_duplicate_source_references(test_settings) -> None:
    query = "How do I reset the device?"
    duplicated_result = _make_result(
        chunk_id="manual.pdf:2:na:1",
        content="Reset the device by holding the reset button.",
        score=0.88,
    )
    retriever = _FakeRetriever(
        response=_make_response(query, [duplicated_result, duplicated_result])
    )
    gemini = _FakeGeminiService(answer="Hold the reset button.")
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=1)

    assert response.grounded is True
    assert len(response.sources) == 1
    assert len(response.retrieved_results) == 1


def test_rag_service_rejects_empty_query(test_settings) -> None:
    rag_service = RAGService(
        test_settings,
        retriever_service=_FakeRetriever(response=_make_response("unused", [])),
        gemini_service=_FakeGeminiService(answer="unused"),
    )

    with pytest.raises(ValidationError, match="empty or whitespace only"):
        rag_service.answer_question("   ", top_k=1)


def test_rag_service_returns_fallback_without_gemini_when_no_results(test_settings) -> None:
    query = "What is the support window?"
    retriever = _FakeRetriever(response=_make_response(query, []))
    gemini = _FakeGeminiService(answer="unused")
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=2)

    assert response.grounded is False
    assert response.answer == FALLBACK_NO_CONTEXT_MESSAGE
    assert response.message == "No relevant context was retrieved from the knowledge base."
    assert "no_results_fallback" in response.graph_nodes_executed
    assert not gemini.calls


def test_rag_service_returns_fallback_for_empty_context(test_settings) -> None:
    query = "How do I reset the router?"
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="manual.pdf:2:na:1",
                    content="Reset procedure details.",
                    score=0.84,
                )
            ],
        )
    )
    gemini = _FakeGeminiService(answer="unused")
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    with patch.object(RAGService, "_build_context", return_value=""):
        response = rag_service.answer_question(query, top_k=1)

    assert response.grounded is False
    assert response.answer == FALLBACK_NO_CONTEXT_MESSAGE
    assert response.message == "Grounded context could not be constructed from the retrieved results."
    assert not gemini.calls


def test_rag_service_handles_gemini_failure_cleanly(test_settings) -> None:
    query = "How do I reset the router?"
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="manual.pdf:2:na:1",
                    content="Reset procedure details.",
                    score=0.84,
                )
            ],
        )
    )
    gemini = _FakeGeminiService(
        error=GenerationError("Gemini request failed during grounded answer generation.")
    )
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=1)

    assert response.grounded is False
    assert response.error == "Gemini request failed during grounded answer generation."
    assert response.message == "Grounded answer generation is currently unavailable."


def test_rag_service_handles_empty_gemini_response(test_settings) -> None:
    query = "How do I reset the router?"
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="manual.pdf:2:na:1",
                    content="Reset procedure details.",
                    score=0.84,
                )
            ],
        )
    )
    gemini = _FakeGeminiService(answer="   ")
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=1)

    assert response.grounded is False
    assert response.answer == FALLBACK_NO_CONTEXT_MESSAGE
    assert response.message == "Gemini returned an empty grounded answer."


def test_rag_service_validates_top_k(test_settings) -> None:
    rag_service = RAGService(
        test_settings,
        retriever_service=_FakeRetriever(response=_make_response("unused", [])),
        gemini_service=_FakeGeminiService(answer="unused"),
    )

    with pytest.raises(ValidationError, match="Top-K must be greater than zero"):
        rag_service.answer_question("How do I reset the router?", top_k=0)


def test_rag_service_filters_weak_results_before_generation(test_settings) -> None:
    query = "What is the capital of France?"
    stricter_settings = replace(
        test_settings,
        app=replace(test_settings.app, rag_relevance_threshold=0.90),
    )
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="manual.pdf:2:na:1",
                    content="Reset procedure details.",
                    score=0.42,
                )
            ],
        )
    )
    gemini = _FakeGeminiService(answer="unused")
    rag_service = RAGService(
        stricter_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=1)

    assert response.grounded is False
    assert response.answer == FALLBACK_NO_CONTEXT_MESSAGE
    assert response.retrieved_chunk_count == 1
    assert response.relevant_chunk_count == 0
    assert "low_relevance_fallback" in response.graph_nodes_executed
    assert not gemini.calls


def test_rag_response_to_dict_includes_phase7_fields() -> None:
    response = RAGResponse(
        query="How do I reset the router?",
        answer="Hold the reset button for ten seconds.",
        grounded=True,
        message="Grounded answer generated successfully.",
        error="",
        sources=[],
        retrieved_results=[],
        reasoning_strategy="SIMPLE_QA",
        graph_nodes_executed=["load_memory", "simple_grounded_answer"],
        retrieved_chunk_count=2,
        relevant_chunk_count=2,
        source_documents=["manual.pdf"],
    )

    serialized = response.to_dict()

    assert serialized["query"] == "How do I reset the router?"
    assert serialized["grounded"] is True
    assert serialized["reasoning_strategy"] == "SIMPLE_QA"
    assert serialized["graph_nodes_executed"] == ["load_memory", "simple_grounded_answer"]
    assert serialized["source_documents"] == ["manual.pdf"]


def test_rag_service_uses_contextualized_query_and_stores_memory(test_settings) -> None:
    query = "What comes after that?"
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="manual.pdf:2:na:1",
                    content="A one-minute break comes after Advanced Coding Easy.",
                    score=0.86,
                )
            ],
        )
    )
    gemini = _FakeGeminiService(answer="A 1-minute breaktime comes after Advanced Coding Easy.")
    contextualizer = _FakeContextualizer(
        resolved_query="What comes after Advanced Coding Easy?"
    )
    memory_storage: dict[str, object] = {}
    memory_service = ConversationMemoryService(
        test_settings,
        storage=memory_storage,
        session_id="test-session",
    )
    memory_service.add_user_message("What is the duration of Advanced Coding Easy?")
    memory_service.add_assistant_message(
        "Advanced Coding Easy has a duration of 35 minutes.",
        grounded=True,
    )
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
        conversation_memory_service=memory_service,
        query_contextualizer=contextualizer,
    )

    response = rag_service.answer_question(query, top_k=1)

    assert response.grounded is True
    assert response.query == "What comes after that?"
    assert response.resolved_query == "What comes after Advanced Coding Easy?"
    assert response.memory_messages_used == 2
    assert retriever.calls == [("What comes after Advanced Coding Easy?", 3)]
    assert gemini.calls[0]["user_question"] == "What comes after that?"
    assert gemini.calls[0]["resolved_query"] == "What comes after Advanced Coding Easy?"
    assert response.graph_nodes_executed[-1] == "update_memory"

    history = memory_service.get_history()
    assert history[-2].role == "user"
    assert history[-2].content == "What comes after that?"
    assert history[-1].role == "assistant"
    assert history[-1].content == "A 1-minute breaktime comes after Advanced Coding Easy."
    assert history[-1].grounded is True


def test_rag_service_falls_back_to_original_query_when_contextualization_fails(
    test_settings,
) -> None:
    query = "What comes after that?"
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="manual.pdf:2:na:1",
                    content="A one-minute break comes after Advanced Coding Easy.",
                    score=0.86,
                )
            ],
        )
    )
    gemini = _FakeGeminiService(
        answer="A 1-minute breaktime comes after Advanced Coding Easy.",
        rewrite_error=GenerationError("Contextualization failed."),
    )
    memory_storage: dict[str, object] = {}
    memory_service = ConversationMemoryService(
        test_settings,
        storage=memory_storage,
        session_id="test-session",
    )
    memory_service.add_user_message("What is the duration of Advanced Coding Easy?")
    memory_service.add_assistant_message(
        "Advanced Coding Easy has a duration of 35 minutes.",
        grounded=True,
    )
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
        conversation_memory_service=memory_service,
        query_contextualizer=QueryContextualizer(
            test_settings,
            gemini_service=gemini,
        ),
    )

    response = rag_service.answer_question(query, top_k=1)

    assert response.grounded is True
    assert response.query == "What comes after that?"
    assert response.resolved_query == "What comes after that?"
    assert retriever.calls == [("What comes after that?", 3)]


def test_rag_service_routes_multi_document_queries_through_synthesis(test_settings) -> None:
    query = "Compare the installation requirements described in these documents."
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="doc-a.pdf:2:na:1",
                    content="Document A requires Python 3.11 and 8 GB RAM.",
                    score=0.92,
                    file_name="doc-a.pdf",
                ),
                _make_result(
                    chunk_id="doc-b.pdf:4:na:1",
                    content="Document B requires Python 3.10, Docker, and 16 GB RAM.",
                    score=0.89,
                    file_name="doc-b.pdf",
                    page_number=4,
                ),
            ],
        )
    )
    gemini = _FakeGeminiService(
        task_responses={
            "document evidence summarization": [
                "Document A requires Python 3.11 and 8 GB RAM.",
                "Document B requires Python 3.10, Docker, and 16 GB RAM.",
            ],
            "multi-document synthesis": (
                "Document A requires Python 3.11 and 8 GB RAM, while Document B "
                "requires Python 3.10, Docker, and 16 GB RAM."
            ),
        }
    )
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=2)

    assert response.grounded is True
    assert response.reasoning_strategy == "MULTI_DOCUMENT_REASONING"
    assert response.answer.startswith("Document A requires Python 3.11")
    assert response.source_documents == ["doc-a.pdf", "doc-b.pdf"]
    assert len(response.document_evidence) == 2
    assert len(response.sources) == 2
    assert not gemini.calls
    assert [
        call["task_name"]
        for call in gemini.task_calls
    ] == [
        "document evidence summarization",
        "document evidence summarization",
        "multi-document synthesis",
    ]
    assert "summarize_document_evidence" in response.graph_nodes_executed
    assert "synthesize_multi_document_answer" in response.graph_nodes_executed


def test_rag_service_handles_multi_document_reasoning_failure_cleanly(test_settings) -> None:
    query = "Compare the installation requirements described in these documents."
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="doc-a.pdf:2:na:1",
                    content="Document A requires Python 3.11 and 8 GB RAM.",
                    score=0.92,
                    file_name="doc-a.pdf",
                ),
                _make_result(
                    chunk_id="doc-b.pdf:4:na:1",
                    content="Document B requires Python 3.10, Docker, and 16 GB RAM.",
                    score=0.89,
                    file_name="doc-b.pdf",
                    page_number=4,
                ),
            ],
        )
    )
    gemini = _FakeGeminiService(
        task_errors={
            "document evidence summarization": GenerationError(
                "Gemini request failed during grounded answer generation."
            )
        }
    )
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=2)

    assert response.grounded is False
    assert response.message == "Grounded answer generation is currently unavailable."
    assert response.error == "Gemini request failed during grounded answer generation."
    assert response.reasoning_strategy == "MULTI_DOCUMENT_REASONING"
    assert "summarize_document_evidence" in response.graph_nodes_executed


def test_rag_service_keeps_simple_path_when_query_is_not_multi_document_reasoning(
    test_settings,
) -> None:
    query = "What is the installation requirement?"
    retriever = _FakeRetriever(
        response=_make_response(
            query,
            [
                _make_result(
                    chunk_id="doc-a.pdf:2:na:1",
                    content="Document A requires Python 3.11 and 8 GB RAM.",
                    score=0.92,
                    file_name="doc-a.pdf",
                ),
                _make_result(
                    chunk_id="doc-b.pdf:4:na:1",
                    content="Document B requires Python 3.10, Docker, and 16 GB RAM.",
                    score=0.89,
                    file_name="doc-b.pdf",
                    page_number=4,
                ),
            ],
        )
    )
    gemini = _FakeGeminiService(answer="The retrieved documents describe installation requirements.")
    rag_service = RAGService(
        test_settings,
        retriever_service=retriever,
        gemini_service=gemini,
    )

    response = rag_service.answer_question(query, top_k=2)

    assert response.grounded is True
    assert response.reasoning_strategy == "SIMPLE_QA"
    assert "simple_grounded_answer" in response.graph_nodes_executed
    assert "summarize_document_evidence" not in response.graph_nodes_executed

