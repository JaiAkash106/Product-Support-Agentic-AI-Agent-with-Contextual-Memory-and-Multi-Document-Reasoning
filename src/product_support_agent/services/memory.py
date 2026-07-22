from __future__ import annotations

from collections.abc import MutableMapping

from product_support_agent.config import Settings
from product_support_agent.logger import get_logger
from product_support_agent.models import ConversationMessage, ConversationState, ServiceStatus


class ConversationMemoryService:
    """Manages session-scoped in-memory conversation history."""

    _STATE_PREFIX = "conversation_memory"

    def __init__(
        self,
        settings: Settings,
        *,
        storage: MutableMapping[str, object] | None = None,
        session_id: str = "default",
    ) -> None:
        self._settings = settings
        self._storage = storage if storage is not None else {}
        self._session_id = session_id
        self._logger = get_logger(__name__)

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def memory_max_turns(self) -> int:
        return self._settings.app.memory_max_turns

    @property
    def _storage_key(self) -> str:
        return f"{self._STATE_PREFIX}:{self.session_id}"

    def add_user_message(self, content: str) -> None:
        self._append_message(ConversationMessage(role="user", content=content))

    def add_assistant_message(self, content: str, *, grounded: bool) -> None:
        self._append_message(
            ConversationMessage(
                role="assistant",
                content=content,
                grounded=grounded,
            )
        )

    def get_history(self) -> list[ConversationMessage]:
        return list(self._get_state().messages)

    def get_recent_history(self) -> list[ConversationMessage]:
        filtered_messages = [
            message
            for message in self.get_history()
            if message.role == "user" or message.grounded is True
        ]
        return filtered_messages[-self.memory_max_turns :]

    def clear_history(self) -> None:
        self._storage[self._storage_key] = ConversationState(session_id=self.session_id)
        self._logger.info("Conversation history cleared: session_id=%s", self.session_id)

    def has_history(self) -> bool:
        return bool(self.get_history())

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="conversation_memory",
            state="ready",
            details=(
                f"Session memory is active for session_id={self.session_id} "
                f"with {len(self.get_history())} stored messages."
            ),
        )

    def _get_state(self) -> ConversationState:
        state = self._storage.get(self._storage_key)
        if not isinstance(state, ConversationState):
            state = ConversationState(session_id=self.session_id)
            self._storage[self._storage_key] = state
        return state

    def _append_message(self, message: ConversationMessage) -> None:
        state = self._get_state()
        state.messages.append(message)
        max_stored_messages = max(self.memory_max_turns * 2, 2)
        if len(state.messages) > max_stored_messages:
            state.messages = state.messages[-max_stored_messages:]
        self._logger.info(
            "Conversation turn added: session_id=%s role=%s grounded=%s total_messages=%s",
            self.session_id,
            message.role,
            message.grounded,
            len(state.messages),
        )


ConversationMemory = ConversationMemoryService
