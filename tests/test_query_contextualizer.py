from __future__ import annotations

from product_support_agent.exceptions import GenerationError
from product_support_agent.models import ConversationMessage
from product_support_agent.services.query_contextualizer import QueryContextualizer


class _FakeLLMService:
    def __init__(self, *, rewrite_answer: str = "", error: Exception | None = None) -> None:
        self._rewrite_answer = rewrite_answer
        self._error = error
        self.calls: list[dict[str, object]] = []

    def contextualize_query(
        self,
        *,
        system_instruction: str,
        conversation_history: str,
        current_query: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "conversation_history": conversation_history,
                "current_query": current_query,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            }
        )
        if self._error is not None:
            raise self._error
        return self._rewrite_answer


def test_query_contextualizer_keeps_standalone_query_valid(test_settings) -> None:
    llm_service = _FakeLLMService(
        rewrite_answer="What is the duration of Advanced Coding Easy?"
    )
    contextualizer = QueryContextualizer(
        test_settings,
        llm_service=llm_service,
    )
    history = [
        ConversationMessage(
            role="user",
            content="Tell me about the assessment sections.",
        )
    ]

    resolved_query = contextualizer.resolve_query(
        current_query="What is the duration of Advanced Coding Easy?",
        history=history,
    )

    assert resolved_query == "What is the duration of Advanced Coding Easy?"
    assert llm_service.calls


def test_query_contextualizer_resolves_follow_up_query_from_history(test_settings) -> None:
    llm_service = _FakeLLMService(
        rewrite_answer="What comes after Advanced Coding Easy?"
    )
    contextualizer = QueryContextualizer(
        test_settings,
        llm_service=llm_service,
    )
    history = [
        ConversationMessage(
            role="user",
            content="What is the duration of Advanced Coding Easy?",
        ),
        ConversationMessage(
            role="assistant",
            content="Advanced Coding Easy has a duration of 35 minutes.",
            grounded=True,
        ),
    ]

    resolved_query = contextualizer.resolve_query(
        current_query="What comes after that?",
        history=history,
    )

    assert resolved_query == "What comes after Advanced Coding Easy?"
    assert llm_service.calls[0]["current_query"] == "What comes after that?"


def test_query_contextualizer_uses_original_query_when_history_is_empty(
    test_settings,
) -> None:
    llm_service = _FakeLLMService(
        rewrite_answer="unused"
    )
    contextualizer = QueryContextualizer(
        test_settings,
        llm_service=llm_service,
    )

    resolved_query = contextualizer.resolve_query(
        current_query="What comes after that?",
        history=[],
    )

    assert resolved_query == "What comes after that?"
    assert not llm_service.calls


def test_query_contextualizer_falls_back_to_original_query_on_failure(
    test_settings,
) -> None:
    llm_service = _FakeLLMService(
        error=GenerationError("Contextualization failed.")
    )
    contextualizer = QueryContextualizer(
        test_settings,
        llm_service=llm_service,
    )
    history = [
        ConversationMessage(
            role="user",
            content="What is the duration of Advanced Coding Easy?",
        ),
        ConversationMessage(
            role="assistant",
            content="Advanced Coding Easy has a duration of 35 minutes.",
            grounded=True,
        ),
    ]

    resolved_query = contextualizer.resolve_query(
        current_query="What comes after that?",
        history=history,
    )

    assert resolved_query == "What comes after that?"
