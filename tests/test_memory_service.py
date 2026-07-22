from __future__ import annotations

from pathlib import Path

from product_support_agent.services.memory import ConversationMemoryService


def test_conversation_memory_adds_and_returns_messages(test_settings) -> None:
    storage: dict[str, object] = {}
    memory_service = ConversationMemoryService(
        test_settings,
        storage=storage,
        session_id="session-1",
    )

    memory_service.add_user_message("What is the duration of Advanced Coding Easy?")
    memory_service.add_assistant_message(
        "Advanced Coding Easy has a duration of 35 minutes.",
        grounded=True,
    )

    history = memory_service.get_history()

    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"
    assert history[1].grounded is True


def test_conversation_memory_returns_limited_recent_history(test_settings) -> None:
    storage: dict[str, object] = {}
    memory_service = ConversationMemoryService(
        test_settings,
        storage=storage,
        session_id="session-1",
    )

    for index in range(8):
        memory_service.add_user_message(f"user-{index}")
        memory_service.add_assistant_message(f"assistant-{index}", grounded=True)

    recent_history = memory_service.get_recent_history()

    assert len(recent_history) == test_settings.app.memory_max_turns
    assert recent_history[0].content == "user-5"
    assert recent_history[-1].content == "assistant-7"


def test_conversation_memory_clear_history_does_not_touch_faiss_files(test_settings) -> None:
    storage: dict[str, object] = {}
    memory_service = ConversationMemoryService(
        test_settings,
        storage=storage,
        session_id="session-1",
    )
    index_file = Path(test_settings.paths.vector_index_file)
    metadata_file = Path(test_settings.paths.vector_metadata_file)
    index_file.write_text("index", encoding="utf-8")
    metadata_file.write_text("metadata", encoding="utf-8")

    memory_service.add_user_message("What comes after that?")
    memory_service.add_assistant_message("A 1-minute break follows.", grounded=False)
    memory_service.clear_history()

    assert memory_service.get_history() == []
    assert index_file.exists()
    assert metadata_file.exists()
