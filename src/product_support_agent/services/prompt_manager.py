from __future__ import annotations

from pathlib import Path

from product_support_agent.config import Settings
from product_support_agent.models import ServiceStatus


DEFAULT_SYSTEM_PROMPT = """You are a product support AI assistant for enterprise users.

Answer the user's question using ONLY the provided context retrieved from the knowledge base.
Do not use outside knowledge.
If the provided context does not contain enough information to answer the question, explicitly state that the answer could not be found in the available knowledge base.
Do not invent facts, procedures, product details, commands, specifications, or supported features.
Use the source identifiers provided with each context block to cite the supporting sources.
Provide a concise and clear answer.
"""

DEFAULT_QUERY_CONTEXTUALIZATION_PROMPT = """You rewrite follow-up user questions into standalone retrieval queries.

Use conversation history only to resolve references such as:
"it", "that", "this", "they", "the previous one", "after that", and "before that".

Do not answer the question.
Do not introduce new facts.
Return only the rewritten standalone query text.
If the current user question is already standalone, return it unchanged except for light normalization.
"""

DEFAULT_DOCUMENT_SUMMARY_PROMPT = """You are preparing grounded evidence notes for a product-support comparison workflow.

Use only the supplied document chunks.
Do not use outside knowledge.
Do not fabricate missing information.
Write a concise evidence summary that captures only details relevant to the user's question.
Preserve the source identifier exactly as provided.
Do not answer the user's question yet.
"""

DEFAULT_MULTI_DOCUMENT_SYNTHESIS_PROMPT = """You are a product support assistant performing multi-document reasoning.

Use only the supplied document evidence summaries.
Do not use outside knowledge.
Do not fabricate missing information.
Compare, contrast, or synthesize the evidence according to the user's question.
If the evidence is insufficient, say so clearly.
Do not expose hidden reasoning steps.
Provide a concise final answer only.
"""


class PromptManager:
    """Owns prompt asset storage and retrieval."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def default_prompt_path(self) -> Path:
        return self._settings.paths.default_prompt_file

    @property
    def query_contextualization_prompt_path(self) -> Path:
        return self._settings.paths.query_contextualization_prompt_file

    @property
    def document_summary_prompt_path(self) -> Path:
        return self._settings.paths.document_summary_prompt_file

    @property
    def multi_document_synthesis_prompt_path(self) -> Path:
        return self._settings.paths.multi_document_synthesis_prompt_file

    def ensure_default_prompt(self) -> None:
        if not self.default_prompt_path.exists():
            self.default_prompt_path.write_text(DEFAULT_SYSTEM_PROMPT, encoding="utf-8")

    def ensure_query_contextualization_prompt(self) -> None:
        if not self.query_contextualization_prompt_path.exists():
            self.query_contextualization_prompt_path.write_text(
                DEFAULT_QUERY_CONTEXTUALIZATION_PROMPT,
                encoding="utf-8",
            )

    def ensure_document_summary_prompt(self) -> None:
        if not self.document_summary_prompt_path.exists():
            self.document_summary_prompt_path.write_text(
                DEFAULT_DOCUMENT_SUMMARY_PROMPT,
                encoding="utf-8",
            )

    def ensure_multi_document_synthesis_prompt(self) -> None:
        if not self.multi_document_synthesis_prompt_path.exists():
            self.multi_document_synthesis_prompt_path.write_text(
                DEFAULT_MULTI_DOCUMENT_SYNTHESIS_PROMPT,
                encoding="utf-8",
            )

    def load_default_prompt(self) -> str:
        self.ensure_default_prompt()
        return self.default_prompt_path.read_text(encoding="utf-8")

    def load_query_contextualization_prompt(self) -> str:
        self.ensure_query_contextualization_prompt()
        return self.query_contextualization_prompt_path.read_text(encoding="utf-8")

    def load_document_summary_prompt(self) -> str:
        self.ensure_document_summary_prompt()
        return self.document_summary_prompt_path.read_text(encoding="utf-8")

    def load_multi_document_synthesis_prompt(self) -> str:
        self.ensure_multi_document_synthesis_prompt()
        return self.multi_document_synthesis_prompt_path.read_text(encoding="utf-8")

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="prompt_manager",
            state="ready",
            details=(
                "Prompt assets are managed at "
                f"{self.default_prompt_path.parent}."
            ),
        )
