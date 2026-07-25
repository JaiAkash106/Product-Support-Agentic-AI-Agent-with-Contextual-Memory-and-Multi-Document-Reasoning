from __future__ import annotations

from product_support_agent.config import Settings
from product_support_agent.exceptions import ConfigurationError
from product_support_agent.services.llm.base import BaseLLMService
from product_support_agent.services.llm.ollama_service import OllamaService


class GeminiLLMAdapter(BaseLLMService):
    """Adapter that exposes the legacy Gemini implementation through the new LLM contract."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        from product_support_agent.services.gemini_service import GeminiService

        self._gemini_service = GeminiService(settings)

    def contextualize_query(
        self,
        *,
        system_instruction: str,
        conversation_history: str,
        current_query: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        return self._gemini_service.generate_text(
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
        return self._gemini_service.generate_answer(
            system_instruction=system_instruction,
            context=context,
            user_question=user_question,
            resolved_query=resolved_query,
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
        return self._gemini_service.generate_text(
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
        return self._gemini_service.generate_text(
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

    def status(self):  # pragma: no cover - thin adapter passthrough
        return self._gemini_service.status()


def build_llm_service(settings: Settings) -> BaseLLMService:
    """Resolve the configured LLM provider without activating it in the app path yet."""

    provider = settings.app.llm_provider.strip().lower()

    
    if provider == "gemini":
        return GeminiLLMAdapter(settings)
    if provider == "ollama":
        return OllamaService(settings)
    raise ConfigurationError(
        f"Unsupported LLM provider '{settings.app.llm_provider}'. "
        "Supported providers are: gemini, ollama."
    )



__all__ = [
    "BaseLLMService",
    "GeminiLLMAdapter",
    "OllamaService",
    "build_llm_service",
]
