from __future__ import annotations

import streamlit as st

from product_support_agent.config import Settings
from product_support_agent.utils import format_supported_extensions


def render_sidebar(settings: Settings) -> None:
    st.sidebar.title("Workspace")
    st.sidebar.caption("Enterprise setup and implementation foundation")

    st.sidebar.markdown("### Runtime")
    st.sidebar.write(f"Environment: `{settings.app.environment}`")
    st.sidebar.write(f"Debug: `{settings.app.debug}`")
    st.sidebar.write(f"Gemini Model: `{settings.app.gemini_model}`")
    st.sidebar.write(
        f"Gemini Configured: `{'yes' if settings.app.gemini_api_key else 'no'}`"
    )

    st.sidebar.markdown("### Supported Files")
    st.sidebar.write(format_supported_extensions(settings.app.supported_extensions))
    st.sidebar.write(f"Max upload size: `{settings.app.max_upload_size_mb} MB`")
    st.sidebar.write(f"Default Top-K: `{settings.app.top_k_results}`")
    st.sidebar.write(
        f"Relevance Threshold: `{settings.app.rag_relevance_threshold}`"
    )
    st.sidebar.write(f"Memory Max Turns: `{settings.app.memory_max_turns}`")

    st.sidebar.markdown("### Storage Paths")
    st.sidebar.write(f"Uploads: `{settings.paths.upload_dir}`")
    st.sidebar.write(f"FAISS: `{settings.paths.faiss_dir}`")
    st.sidebar.write(f"Metadata: `{settings.paths.metadata_dir}`")
    st.sidebar.write(f"Logs: `{settings.paths.log_dir}`")
    st.sidebar.write(f"Prompts: `{settings.paths.prompt_dir}`")
