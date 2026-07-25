from __future__ import annotations

from product_support_agent.config import Settings
from product_support_agent.exceptions import ContextualizationError, ProductSupportAgentError
from product_support_agent.logger import get_logger
from product_support_agent.models import ConversationMessage, ServiceStatus
from product_support_agent.services.llm import build_llm_service
from product_support_agent.services.llm.base import BaseLLMService
from product_support_agent.services.prompt_manager import PromptManager


class QueryContextualizer:
    """Rewrites conversational follow-up questions into standalone retrieval queries."""

    def __init__(
        self,
        settings: Settings,
        *,
        llm_service: BaseLLMService | None = None,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        self._settings = settings
        self._llm_service = llm_service or build_llm_service(settings)
        self._prompt_manager = prompt_manager or PromptManager(settings)
        self._logger = get_logger(__name__)

    def resolve_query(
        self,
        *,
        current_query: str,
        history: list[ConversationMessage],
    ) -> str:
        normalized_query = " ".join(current_query.split())
        if not normalized_query:
            raise ContextualizationError("Current query cannot be empty for contextualization.")

        if not history:
            self._logger.info(
                "Contextualization skipped because no conversation history is available."
            )
            return normalized_query

        prompt = self._prompt_manager.load_query_contextualization_prompt()
        contents = self._build_contextualization_contents(
            history=history,
            current_query=normalized_query,
        )

        self._logger.info(
            "Contextualization started: history_messages=%s original_query_length=%s",
            len(history),
            len(normalized_query),
        )
        try:
            resolved_query = self._llm_service.contextualize_query(
                system_instruction=prompt,
                conversation_history=self._extract_history_block(contents),
                current_query=normalized_query,
                temperature=self._settings.app.contextualizer_temperature,
                max_output_tokens=self._settings.app.contextualizer_max_output_tokens,
            )
        except ProductSupportAgentError as exc:
            self._logger.warning(
                "Contextualization fallback triggered: original_query=%s error=%s",
                normalized_query,
                str(exc),
            )
            return normalized_query

        cleaned_query = " ".join(resolved_query.split())
        if not cleaned_query:
            self._logger.warning(
                "Contextualization produced an empty query. Falling back to the original query."
            )
            return normalized_query

        self._logger.info(
            "Contextualization completed successfully: original_query=%s resolved_query=%s",
            normalized_query,
            cleaned_query,
        )
        return cleaned_query

    @staticmethod
    def _build_contextualization_contents(
        *,
        history: list[ConversationMessage],
        current_query: str,
    ) -> str:
        history_lines = []
        for message in history:
            role_label = "User" if message.role == "user" else "Assistant"
            history_lines.append(f"{role_label}: {message.content}")

        history_block = "\n".join(history_lines) if history_lines else "No prior history."
        return (
            f"CONVERSATION HISTORY:\n{history_block}\n\n"
            f"CURRENT USER QUESTION:\n{current_query}\n\n"
            "REWRITTEN STANDALONE QUERY:\n"
        )

    @staticmethod
    def _extract_history_block(contents: str) -> str:
        history_marker = "CONVERSATION HISTORY:\n"
        current_question_marker = "\n\nCURRENT USER QUESTION:\n"

        if history_marker not in contents or current_question_marker not in contents:
            return contents

        history_start = len(history_marker)
        history_end = contents.index(current_question_marker)
        return contents[history_start:history_end].strip()

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="query_contextualizer",
            state="ready",
            details=(
                "Query contextualization is enabled with "
                f"memory_max_turns={self._settings.app.memory_max_turns}."
            ),
        )
