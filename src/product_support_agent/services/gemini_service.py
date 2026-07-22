from __future__ import annotations

from enum import Enum
from typing import Any

from product_support_agent.config import Settings
from product_support_agent.exceptions import ConfigurationError, GenerationError
from product_support_agent.logger import get_logger
from product_support_agent.models import ServiceStatus


class GeminiService:
    """Handles grounded text generation through the official Gemini SDK."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = get_logger(__name__)
        self._client: Any | None = None

    @property
    def model_name(self) -> str:
        return self._settings.app.gemini_model

    @property
    def api_key(self) -> str:
        return self._settings.app.gemini_api_key

    def is_configured(self) -> bool:
        return bool(self.api_key.strip())

    def generate_answer(
        self,
        *,
        system_instruction: str,
        context: str,
        user_question: str,
        resolved_query: str | None = None,
    ) -> str:
        if not self.is_configured():
            raise ConfigurationError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in the environment."
            )
        if not context.strip():
            raise GenerationError("Grounded answer generation requires non-empty context.")

        self._logger.info(
            "Starting Gemini grounded generation: model=%s question_length=%s context_length=%s",
            self.model_name,
            len(user_question),
            len(context),
        )
        generated_text = self.generate_text(
            system_instruction=system_instruction,
            user_content=self._build_contents(
                context=context,
                user_question=user_question,
                resolved_query=resolved_query,
            ),
            temperature=self._settings.app.gemini_temperature,
            max_output_tokens=self._settings.app.gemini_max_output_tokens,
            task_name="grounded generation",
        )
        self._logger.info("Gemini grounded generation completed successfully.")
        return generated_text

    def generate_text(
        self,
        *,
        system_instruction: str,
        user_content: str,
        temperature: float,
        max_output_tokens: int,
        task_name: str,
    ) -> str:
        if not self.is_configured():
            raise ConfigurationError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in the environment."
            )
        if not user_content.strip():
            raise GenerationError(f"Gemini {task_name} requires non-empty input content.")

        client, sdk_types = self._load_client_and_types()
        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=sdk_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )
        except Exception as exc:  # pragma: no cover - SDK/runtime-specific path
            raise self._map_generation_exception(exc) from exc

        candidates = list(getattr(response, "candidates", None) or [])
        candidate_count = len(candidates)
        finish_reason = self._extract_finish_reason(candidates[0] if candidates else None)
        usage_metadata = getattr(response, "usage_metadata", None)
        generated_text = (getattr(response, "text", "") or "").strip()

        self._logger.info(
            "Gemini %s response received: candidate_count=%s finish_reason=%s usage_metadata=%s generated_text_length=%s",
            task_name,
            candidate_count,
            finish_reason,
            usage_metadata,
            len(generated_text),
        )

        if candidate_count == 0:
            raise GenerationError(f"Gemini returned no candidates for {task_name}.")
        if not generated_text:
            raise GenerationError(f"Gemini returned an empty response for {task_name}.")
        if not self._is_successful_finish_reason(finish_reason):
            self._logger.warning(
                "Gemini %s ended with non-success finish reason: %s",
                task_name,
                finish_reason,
            )
            raise GenerationError(
                f"Gemini returned an incomplete or blocked response for {task_name}."
            )
        return generated_text

    def _load_client_and_types(self) -> tuple[Any, Any]:
        if self._client is not None:
            sdk_types = self._load_sdk_types()
            return self._client, sdk_types

        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - depends on environment setup
            raise ConfigurationError(
                "The official Gemini SDK is not installed. Install the 'google-genai' package."
            ) from exc

        self._client = genai.Client(api_key=self.api_key)
        return self._client, self._load_sdk_types()

    @staticmethod
    def _load_sdk_types() -> Any:
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - depends on environment setup
            raise ConfigurationError(
                "The official Gemini SDK is not installed. Install the 'google-genai' package."
            ) from exc
        return types

    @staticmethod
    def _build_contents(
        *,
        context: str,
        user_question: str,
        resolved_query: str | None = None,
    ) -> str:
        lines = [
            f"CONTEXT BLOCKS:\n{context}",
            f"USER QUESTION:\n{user_question}",
        ]
        if resolved_query and resolved_query != user_question:
            lines.append(
                "RESOLVED RETRIEVAL QUERY:\n"
                f"{resolved_query}"
            )
        lines.append("ANSWER:\n")
        return "\n\n".join(lines)

    @staticmethod
    def _extract_finish_reason(candidate: Any | None) -> str:
        if candidate is None:
            return "NO_CANDIDATE"

        raw_finish_reason = getattr(candidate, "finish_reason", None)
        if raw_finish_reason is None:
            return "UNKNOWN"
        if isinstance(raw_finish_reason, str):
            normalized_value = raw_finish_reason
        elif isinstance(raw_finish_reason, Enum):
            normalized_value = str(raw_finish_reason.value)
        else:
            normalized_value = str(
                getattr(raw_finish_reason, "value", None)
                or getattr(raw_finish_reason, "name", None)
                or raw_finish_reason
            )

        normalized_value = normalized_value.strip()
        if "." in normalized_value:
            normalized_value = normalized_value.rsplit(".", maxsplit=1)[-1]
        return normalized_value.upper() or "UNKNOWN"

    @staticmethod
    def _is_successful_finish_reason(finish_reason: str) -> bool:
        return finish_reason == "STOP"

    def _map_generation_exception(self, exc: Exception) -> GenerationError:
        message = str(exc).lower()
        exception_name = exc.__class__.__name__.lower()

        self._logger.exception("Gemini grounded generation failed.")

        if "auth" in exception_name or "permission" in message or "api key" in message:
            return GenerationError(
                "Gemini authentication failed. Verify that GEMINI_API_KEY is valid."
            )
        if "rate" in message or "quota" in message:
            return GenerationError(
                "Gemini request was rate limited. Please retry after a short delay."
            )
        if "timeout" in message or "network" in message or "connection" in message:
            return GenerationError(
                "Gemini request failed because of a network or timeout issue."
            )
        return GenerationError("Gemini request failed during grounded answer generation.")

    def status(self) -> ServiceStatus:
        state = "ready" if self.is_configured() else "configuration_required"
        details = (
            f"Gemini model configured as {self.model_name}. "
            "Grounded answer generation is enabled when GEMINI_API_KEY is available."
        )
        return ServiceStatus(name="gemini_service", state=state, details=details)
