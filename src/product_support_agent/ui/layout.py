from __future__ import annotations

import streamlit as st

from product_support_agent.config import Settings
from product_support_agent.logger import get_logger
from product_support_agent.ui.presenter import build_sidebar_snapshot
from product_support_agent.ui.sections import (
    render_rag_section,
    render_upload_section,
)
from product_support_agent.ui.sidebar import render_sidebar
from product_support_agent.ui.theme import apply_enterprise_theme, render_shell_header


def _configure_page(settings: Settings) -> None:
    st.set_page_config(
        page_title=settings.app.page_title,
        page_icon=settings.app.page_icon,
        layout=settings.app.layout,
        initial_sidebar_state="expanded",
    )


def render_app(settings: Settings) -> None:
    logger = get_logger(__name__)
    _configure_page(settings)
    apply_enterprise_theme()

    sidebar_snapshot = build_sidebar_snapshot(settings)
    render_sidebar(settings, sidebar_snapshot)

    if sidebar_snapshot["provider"] == "ollama":
        status_badge = (
            "Local AI Connected"
            if sidebar_snapshot["connected"]
            else "Local AI Offline"
        )
    else:
        status_badge = (
            "Cloud AI Connected"
            if sidebar_snapshot["connected"]
            else "Cloud AI Offline"
        )

    metrics = [
        {
            "title": "Documents",
            "icon": "\U0001F4C4",
            "value": str(sidebar_snapshot["indexed_documents"]),
            "caption": f"Updated {sidebar_snapshot['last_indexing_time']}",
        },
        {
            "title": "Chunks",
            "icon": "\U0001F9E0",
            "value": str(sidebar_snapshot["knowledge_chunks"]),
            "caption": "Knowledge ready to search",
        },
        {
            "title": "Turns",
            "icon": "\U0001F4AC",
            "value": str(sidebar_snapshot["memory_turns"]),
            "caption": "Answers in this session",
        },
        {
            "title": "Sources",
            "icon": "\U0001F4DA",
            "value": str(sidebar_snapshot["retrieved_documents"]),
            "caption": "Used in the latest answer",
        },
    ]
    if sidebar_snapshot["response_time"] != "Waiting":
        metrics.append(
            {
                "title": "Latest Response",
                "icon": "\u23F1",
                "value": str(sidebar_snapshot["response_time"]),
                "caption": f"Provider: {sidebar_snapshot['provider_label']}",
            }
        )

    render_shell_header(
        title="Product Support AI",
        subtitle="Enterprise Knowledge Assistant powered by Retrieval-Augmented Generation",
        status_badge=status_badge,
        provider_label=str(sidebar_snapshot["provider_label"]),
        model_name=str(sidebar_snapshot["model_name"]),
        metrics=metrics,
        connected=bool(sidebar_snapshot["connected"]),
    )

    navigation = st.segmented_control(
        "Navigation",
        options=["\U0001F4AC Ask AI", "\U0001F4E4 Ingestion"],
        default="\U0001F4AC Ask AI",
        selection_mode="single",
        label_visibility="collapsed",
        width="stretch",
        key="primary_navigation",
    )

    if navigation == "\U0001F4E4 Ingestion":
        render_upload_section(settings)
    else:
        render_rag_section(settings)

    logger.info("Streamlit foundation UI rendered successfully.")
