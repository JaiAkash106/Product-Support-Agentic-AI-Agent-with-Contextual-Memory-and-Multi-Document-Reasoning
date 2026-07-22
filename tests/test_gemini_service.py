from __future__ import annotations

from dataclasses import replace
from enum import Enum

import pytest

from product_support_agent.exceptions import ConfigurationError, GenerationError
from product_support_agent.services.gemini_service import GeminiService


class _FakeGenerateContentConfig:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class _FakeTypes:
    GenerateContentConfig = _FakeGenerateContentConfig


class _FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        candidates: list[object] | None = None,
        usage_metadata: object | None = None,
    ) -> None:
        self.text = text
        self.candidates = candidates
        self.usage_metadata = usage_metadata


class _FakeFinishReason(Enum):
    STOP = "STOP"
    MAX_TOKENS = "MAX_TOKENS"
    OTHER = "OTHER"


class _FakeCandidate:
    def __init__(self, finish_reason: object | None) -> None:
        self.finish_reason = finish_reason


class _FakeModels:
    def __init__(
        self,
        response_text: str,
        *,
        candidates: list[object] | None = None,
        usage_metadata: object | None = None,
    ) -> None:
        self._response_text = response_text
        self._candidates = candidates
        self._usage_metadata = usage_metadata
        self.calls: list[dict[str, object]] = []

    def generate_content(self, *, model: str, contents: str, config: object) -> _FakeResponse:
        self.calls.append(
            {
                "model": model,
                "contents": contents,
                "config": config,
            }
        )
        return _FakeResponse(
            self._response_text,
            candidates=self._candidates,
            usage_metadata=self._usage_metadata,
        )


class _FakeClient:
    def __init__(
        self,
        response_text: str,
        *,
        candidates: list[object] | None = None,
        usage_metadata: object | None = None,
    ) -> None:
        self.models = _FakeModels(
            response_text,
            candidates=candidates,
            usage_metadata=usage_metadata,
        )


def test_gemini_service_requires_api_key(test_settings) -> None:
    service = GeminiService(test_settings)

    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        service.generate_answer(
            system_instruction="Use only the provided context.",
            context="[SOURCE 1]\nContent:\nReset procedure.",
            user_question="How do I reset the router?",
        )


def test_gemini_service_returns_generated_text(test_settings) -> None:
    configured_settings = replace(
        test_settings,
        app=replace(test_settings.app, gemini_api_key="test-key"),
    )
    service = GeminiService(configured_settings)
    fake_client = _FakeClient(
        "Use the reset button for ten seconds.",
        candidates=[_FakeCandidate(_FakeFinishReason.STOP)],
        usage_metadata={"prompt_token_count": 100, "response_token_count": 12},
    )
    service._load_client_and_types = lambda: (fake_client, _FakeTypes)  # type: ignore[method-assign]

    answer = service.generate_answer(
        system_instruction="Use only the provided context.",
        context="[SOURCE 1]\nContent:\nReset procedure.",
        user_question="How do I reset the router?",
    )

    assert answer == "Use the reset button for ten seconds."
    assert fake_client.models.calls[0]["model"] == configured_settings.app.gemini_model
    assert "USER QUESTION" in str(fake_client.models.calls[0]["contents"])


def test_gemini_service_rejects_max_tokens_finish_reason(test_settings) -> None:
    configured_settings = replace(
        test_settings,
        app=replace(test_settings.app, gemini_api_key="test-key"),
    )
    service = GeminiService(configured_settings)
    fake_client = _FakeClient(
        "Based on the provided context, the duration is",
        candidates=[_FakeCandidate(_FakeFinishReason.MAX_TOKENS)],
        usage_metadata={"response_token_count": 20},
    )
    service._load_client_and_types = lambda: (fake_client, _FakeTypes)  # type: ignore[method-assign]

    with pytest.raises(GenerationError, match="incomplete or blocked response"):
        service.generate_answer(
            system_instruction="Use only the provided context.",
            context="[SOURCE 1]\nContent:\nBreaktime 1",
            user_question="What is the time duration between the coding sessions?",
        )


def test_gemini_service_rejects_other_finish_reason(test_settings) -> None:
    configured_settings = replace(
        test_settings,
        app=replace(test_settings.app, gemini_api_key="test-key"),
    )
    service = GeminiService(configured_settings)
    fake_client = _FakeClient(
        "Based on the provided context, the duration is",
        candidates=[_FakeCandidate(_FakeFinishReason.OTHER)],
        usage_metadata={"response_token_count": 18},
    )
    service._load_client_and_types = lambda: (fake_client, _FakeTypes)  # type: ignore[method-assign]

    with pytest.raises(GenerationError, match="incomplete or blocked response"):
        service.generate_answer(
            system_instruction="Use only the provided context.",
            context="[SOURCE 1]\nContent:\nBreaktime 1",
            user_question="What is the time duration between the coding sessions?",
        )


def test_gemini_service_rejects_missing_candidates(test_settings) -> None:
    configured_settings = replace(
        test_settings,
        app=replace(test_settings.app, gemini_api_key="test-key"),
    )
    service = GeminiService(configured_settings)
    fake_client = _FakeClient(
        "Hold the reset button for ten seconds.",
        candidates=[],
        usage_metadata={"response_token_count": 10},
    )
    service._load_client_and_types = lambda: (fake_client, _FakeTypes)  # type: ignore[method-assign]

    with pytest.raises(GenerationError, match="no candidates"):
        service.generate_answer(
            system_instruction="Use only the provided context.",
            context="[SOURCE 1]\nContent:\nReset procedure.",
            user_question="How do I reset the router?",
        )


def test_gemini_service_rejects_empty_response(test_settings) -> None:
    configured_settings = replace(
        test_settings,
        app=replace(test_settings.app, gemini_api_key="test-key"),
    )
    service = GeminiService(configured_settings)
    fake_client = _FakeClient(
        "   ",
        candidates=[_FakeCandidate(_FakeFinishReason.STOP)],
        usage_metadata={"response_token_count": 0},
    )
    service._load_client_and_types = lambda: (fake_client, _FakeTypes)  # type: ignore[method-assign]

    with pytest.raises(GenerationError, match="empty response"):
        service.generate_answer(
            system_instruction="Use only the provided context.",
            context="[SOURCE 1]\nContent:\nReset procedure.",
            user_question="How do I reset the router?",
        )
