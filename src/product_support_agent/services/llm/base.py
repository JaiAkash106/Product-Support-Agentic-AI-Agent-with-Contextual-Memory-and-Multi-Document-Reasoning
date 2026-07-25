from __future__ import annotations

from abc import ABC, abstractmethod

from product_support_agent.config import Settings


class BaseLLMService(ABC):
    """Common provider contract for local or remote text-generation backends."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @abstractmethod
    def contextualize_query(
        self,
        *,
        system_instruction: str,
        conversation_history: str,
        current_query: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Resolve a follow-up question into a standalone retrieval query."""

    @abstractmethod
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
        """Generate a grounded answer from retrieved document context."""

    @abstractmethod
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
        """Summarize evidence for a single retrieved document."""

    @abstractmethod
    def synthesize_documents(
        self,
        *,
        system_instruction: str,
        user_question: str,
        document_evidence: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Synthesize a final answer from per-document evidence summaries."""

    def generate_answer(
        self,
        *,
        system_instruction: str,
        context: str,
        user_question: str,
        resolved_query: str | None = None,
    ) -> str:
        """Compatibility wrapper matching the current GeminiService public API."""

        return self.generate_grounded_answer(
            system_instruction=system_instruction,
            context=context,
            user_question=user_question,
            resolved_query=resolved_query,
            temperature=self._settings.app.gemini_temperature,
            max_output_tokens=self._settings.app.gemini_max_output_tokens,
        )

    def generate_text(
        self,
        *,
        system_instruction: str,
        user_content: str,
        temperature: float,
        max_output_tokens: int,
        task_name: str,
    ) -> str:
        """Compatibility wrapper for incremental migration from GeminiService."""

        normalized_task_name = task_name.strip().lower()
        if normalized_task_name == "query contextualization":
            history_block, current_query = self._split_contextualization_payload(user_content)
            return self.contextualize_query(
                system_instruction=system_instruction,
                conversation_history=history_block,
                current_query=current_query,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        if normalized_task_name == "document evidence summarization":
            user_question, file_name, document_context = self._split_document_summary_payload(
                user_content
            )
            return self.summarize_document(
                system_instruction=system_instruction,
                user_question=user_question,
                file_name=file_name,
                document_context=document_context,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        if normalized_task_name == "multi-document synthesis":
            user_question, document_evidence = self._split_document_synthesis_payload(
                user_content
            )
            return self.synthesize_documents(
                system_instruction=system_instruction,
                user_question=user_question,
                document_evidence=document_evidence,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        raise NotImplementedError(
            f"Task '{task_name}' is not supported through the compatibility layer."
        )

    @staticmethod
    def _split_contextualization_payload(user_content: str) -> tuple[str, str]:
        history_marker = "CONVERSATION HISTORY:\n"
        current_question_marker = "\n\nCURRENT USER QUESTION:\n"
        rewritten_marker = "\n\nREWRITTEN STANDALONE QUERY:\n"

        if (
            history_marker not in user_content
            or current_question_marker not in user_content
            or rewritten_marker not in user_content
        ):
            return "", user_content.strip()

        history_start = len(history_marker)
        history_end = user_content.index(current_question_marker)
        current_query_start = history_end + len(current_question_marker)
        current_query_end = user_content.index(rewritten_marker)

        history_block = user_content[history_start:history_end].strip()
        current_query = user_content[current_query_start:current_query_end].strip()
        return history_block, current_query

    @staticmethod
    def _split_document_summary_payload(user_content: str) -> tuple[str, str, str]:
        question_marker = "USER QUESTION:\n"
        file_marker = "\n\nDOCUMENT FILE:\n"
        summary_marker = "\n\nEVIDENCE SUMMARY:\n"

        if (
            question_marker not in user_content
            or file_marker not in user_content
            or summary_marker not in user_content
        ):
            return "", "", user_content.strip()

        question_start = len(question_marker)
        question_end = user_content.index(file_marker)
        file_name_start = question_end + len(file_marker)
        file_name_end = user_content.index("\n\n[DOCUMENT SOURCE 1]")
        context_end = user_content.index(summary_marker)

        user_question = user_content[question_start:question_end].strip()
        file_name = user_content[file_name_start:file_name_end].strip()
        document_context = user_content[file_name_end + 2:context_end].strip()
        return user_question, file_name, document_context

    @staticmethod
    def _split_document_synthesis_payload(user_content: str) -> tuple[str, str]:
        question_marker = "USER QUESTION:\n"
        answer_marker = "\n\nFINAL ANSWER:\n"

        if question_marker not in user_content or answer_marker not in user_content:
            return "", user_content.strip()

        question_start = len(question_marker)
        question_end = user_content.index("\n\n[DOCUMENT EVIDENCE 1]")
        evidence_start = question_end + 2
        evidence_end = user_content.index(answer_marker)

        user_question = user_content[question_start:question_end].strip()
        document_evidence = user_content[evidence_start:evidence_end].strip()
        return user_question, document_evidence
