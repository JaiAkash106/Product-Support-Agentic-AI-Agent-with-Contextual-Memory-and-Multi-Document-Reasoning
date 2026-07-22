from __future__ import annotations

import streamlit as st

from product_support_agent.config import Settings
from product_support_agent.logger import get_logger
from product_support_agent.ui.sections import (
    render_rag_section,
    render_logs_section,
    render_pipeline_notes_section,
    render_retrieval_section,
    render_upload_section,
)
from product_support_agent.ui.sidebar import render_sidebar


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
    render_sidebar(settings)

    st.title(settings.app.app_name)
    st.caption(f"{settings.app.company_name} | Environment: {settings.app.environment}")
    st.write(settings.app.description)

    upload_tab, retrieval_tab, rag_tab, notes_tab, logs_tab = st.tabs(
        ["Ingestion", "Retrieval", "Ask Knowledge Base", "Pipeline Notes", "Logs"]
    )

    with upload_tab:
        render_upload_section(settings)

    with retrieval_tab:
        render_retrieval_section(settings)

    with rag_tab:
        render_rag_section(settings)

    with notes_tab:
        render_pipeline_notes_section(settings)

    with logs_tab:
        render_logs_section(settings)

    logger.info("Streamlit foundation UI rendered successfully.")
