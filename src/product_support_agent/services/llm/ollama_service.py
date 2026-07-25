from __future__ import annotations

from typing import Any

from product_support_agent.config import Settings
from product_support_agent.exceptions import ConfigurationError, GenerationError
from product_support_agent.logger import get_logger
from product_support_agent.models import ServiceStatus
from product_support_agent.services.llm.base import BaseLLMService


class OllamaService(BaseLLMService):
    """Local LLM provider backed by the official Ollama Python client."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._logger = get_logger(__name__)
        self._client: Any | None = None

    @property
    def model_name(self) -> str:
        return self._settings.app.ollama_model

    @property
    def base_url(self) -> str:
        return self._settings.app.ollama_base_url

    def is_configured(self) -> bool:
        return bool(self.model_name.strip()) and bool(self.base_url.strip())

    def contextualize_query(
        self,
        *,
        system_instruction: str,
        conversation_history: str,
        current_query: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        return self._chat(
            system_instruction=system_instruction,
            user_content=(
                f"CONVERSATION HISTORY:\n{conversation_history}\n\n"
                f"CURRENT USER QUESTION:\n{current_query}\n\n"
                "REWRITTEN STANDALONE QUERY:\n"
            ),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            task_name="query contextualization",
        )

    def generate_grounded_answer(
        self,
        *,
        system_instruction: str,
        context: str,
        user_question: str,
        resolved_query: str | None,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        return self._chat(
            system_instruction=system_instruction,
            user_content=self._build_grounded_answer_contents(
                context=context,
                user_question=user_question,
                resolved_query=resolved_query,
            ),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            task_name="grounded generation",
        )

    def summarize_document(
        self,
        *,
        system_instruction: str,
        user_question: str,
        file_name: str,
        document_context: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        return self._chat(
            system_instruction=system_instruction,
            user_content=(
                f"USER QUESTION:\n{user_question}\n\n"
                f"DOCUMENT FILE:\n{file_name}\n\n"
                f"{document_context}\n\n"
                "EVIDENCE SUMMARY:\n"
            ),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            task_name="document evidence summarization",
        )

    def synthesize_documents(
        self,
        *,
        system_instruction: str,
        user_question: str,
        document_evidence: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        return self._chat(
            system_instruction=system_instruction,
            user_content=(
                f"USER QUESTION:\n{user_question}\n\n"
                f"{document_evidence}\n\n"
                "FINAL ANSWER:\n"
            ),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            task_name="multi-document synthesis",
        )

    def _chat(
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
                "Ollama is not configured. Set OLLAMA_MODEL and OLLAMA_BASE_URL in the environment."
            )
        if not user_content.strip():
            raise GenerationError(f"Ollama {task_name} requires non-empty input content.")

        client = self._load_client()
        self._logger.info(
            "Starting Ollama %s: model=%s base_url=%s input_length=%s",
            task_name,
            self.model_name,
            self.base_url,
            len(user_content),
        )

        try:
            response = client.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content},
                ],
                options={
                    "temperature": temperature,
                    "num_predict": max_output_tokens,
                },
            )
        except Exception as exc:  # pragma: no cover - runtime/provider specific path
            raise self._map_generation_exception(exc, task_name) from exc

        generated_text = self._extract_message_content(response).strip()
        done = self._extract_field(response, "done")
        done_reason = str(self._extract_field(response, "done_reason") or "").strip().lower()
        prompt_eval_count = self._extract_field(response, "prompt_eval_count")
        eval_count = self._extract_field(response, "eval_count")

        self._logger.info(
            "Ollama %s response received: done=%s done_reason=%s prompt_eval_count=%s eval_count=%s generated_text_length=%s",
            task_name,
            done,
            done_reason or "unknown",
            prompt_eval_count,
            eval_count,
            len(generated_text),
        )

        if not generated_text:
            raise GenerationError(f"Ollama returned an empty response for {task_name}.")
        if not self._is_successful_completion(done=done, done_reason=done_reason):
            self._logger.warning(
                "Ollama %s ended with non-success completion state: done=%s done_reason=%s",
                task_name,
                done,
                done_reason or "unknown",
            )
            raise GenerationError(
                f"Ollama returned an incomplete or blocked response for {task_name}."
            )
        return generated_text

    def _load_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from ollama import Client
        except ImportError as exc:  # pragma: no cover - depends on environment setup
            raise ConfigurationError(
                "The official Ollama Python package is not installed. Install the 'ollama' package."
            ) from exc

        self._client = Client(host=self.base_url)
        return self._client

    @staticmethod
    def _build_grounded_answer_contents(
        *,
        context: str,
        user_question: str,
        resolved_query: str | None,
    ) -> str:
        lines = [
            f"CONTEXT BLOCKS:\n{context}",
            f"USER QUESTION:\n{user_question}",
        ]
        if resolved_query and resolved_query != user_question:
            lines.append(f"RESOLVED RETRIEVAL QUERY:\n{resolved_query}")
        lines.append("ANSWER:\n")
        return "\n\n".join(lines)

    @staticmethod
    def _extract_message_content(response: Any) -> str:
        if isinstance(response, dict):
            message = response.get("message", {})
            if isinstance(message, dict):
                return str(message.get("content", "") or "")
            return str(message or "")

        message = getattr(response, "message", None)
        if isinstance(message, dict):
            return str(message.get("content", "") or "")
        if message is not None:
            return str(getattr(message, "content", "") or "")
        return str(getattr(response, "response", "") or "")

    @staticmethod
    def _extract_field(response: Any, field_name: str) -> Any:
        if isinstance(response, dict):
            return response.get(field_name)
        return getattr(response, field_name, None)

    @staticmethod
    def _is_successful_completion(*, done: Any, done_reason: str) -> bool:
        if done is False:
            return False
        return done_reason in {"", "stop"}

    def _map_generation_exception(self, exc: Exception, task_name: str) -> GenerationError:
        message = str(exc).lower()
        exception_name = exc.__class__.__name__.lower()

        self._logger.exception("Ollama %s failed.", task_name)

        if "connection" in message or "refused" in message or "timeout" in message:
            return GenerationError(
                "Ollama request failed because the local Ollama server is unavailable."
            )
        if "not found" in message or "model" in message and "pull" in message:
            return GenerationError(
                f"Ollama model '{self.model_name}' is not available locally. Pull the model and retry."
            )
        if "auth" in exception_name:
            return GenerationError("Ollama authentication failed.")
        return GenerationError(f"Ollama request failed during {task_name}.")

    def status(self) -> ServiceStatus:
        state = "ready" if self.is_configured() else "configuration_required"
        details = (
            f"Ollama model configured as {self.model_name} at {self.base_url}. "
            "Local grounded generation is enabled when the Ollama server is running."
        )
        return ServiceStatus(name="ollama_service", state=state, details=details)
