from __future__ import annotations

import html
from textwrap import dedent

import streamlit as st


ACCENT = "#3B82F6"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
ERROR = "#EF4444"
SURFACE = "#101827"
SURFACE_ALT = "#172033"
SURFACE_MUTED = "#1E293B"
BORDER = "rgba(148, 163, 184, 0.16)"
TEXT = "#E5EEF9"
TEXT_MUTED = "#94A3B8"


def apply_enterprise_theme() -> None:
    st.markdown(
        f"""
        <style>
            :root {{
                --psa-accent: {ACCENT};
                --psa-success: {SUCCESS};
                --psa-warning: {WARNING};
                --psa-error: {ERROR};
                --psa-surface: {SURFACE};
                --psa-surface-alt: {SURFACE_ALT};
                --psa-surface-muted: {SURFACE_MUTED};
                --psa-border: {BORDER};
                --psa-text: {TEXT};
                --psa-text-muted: {TEXT_MUTED};
            }}

            .stApp {{
                background:
                    radial-gradient(circle at top left, rgba(59, 130, 246, 0.18), transparent 28%),
                    radial-gradient(circle at top right, rgba(34, 197, 94, 0.10), transparent 24%),
                    linear-gradient(180deg, #07101c 0%, #0b1424 48%, #09111e 100%);
                color: var(--psa-text);
            }}

            header[data-testid="stHeader"],
            [data-testid="stToolbar"],
            [data-testid="stDecoration"],
            [data-testid="stStatusWidget"],
            [data-testid="stMainMenu"],
            [data-testid="stAppDeployButton"],
            .stAppDeployButton,
            #MainMenu,
            footer {{
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
            }}

            .block-container {{
                max-width: 1480px;
                padding-top: 0.55rem;
                padding-bottom: 1rem;
            }}

            [data-testid="stAppViewContainer"] {{
                padding-top: 0 !important;
            }}

            [data-testid="stSidebar"] {{
                background: linear-gradient(180deg, #091321 0%, #0e1829 100%);
                border-right: 1px solid var(--psa-border);
            }}

            [data-testid="stSidebar"][aria-expanded="true"] > div:first-child,
            [data-testid="stSidebar"][aria-expanded="false"] > div:first-child {{
                width: 320px;
                min-width: 320px;
            }}

            [data-testid="stSidebar"][aria-expanded="false"] > div:first-child {{
                margin-left: 0;
            }}

            [data-testid="stSidebarCollapsedControl"],
            [data-testid="collapsedControl"] {{
                display: none !important;
                visibility: hidden !important;
            }}

            [data-testid="stSidebar"] .block-container {{
                padding-top: 1rem;
            }}

            h1, h2, h3, h4, h5, h6,
            p, label, .stMarkdown, .stCaption, .stText {{
                color: var(--psa-text);
            }}

            [data-testid="stButtonGroup"] {{
                margin: 0.15rem 0 0.35rem 0;
            }}

            [data-testid="stButtonGroup"] [role="radiogroup"] {{
                gap: 0.95rem;
                display: flex;
                flex-wrap: wrap;
            }}

            [data-testid="stButtonGroup"] button[data-variant="segmented_control"] {{
                min-height: 62px !important;
                padding: 0.95rem 1.55rem !important;
                border-radius: 999px !important;
                background: rgba(15, 23, 42, 0.68) !important;
                border: 1px solid var(--psa-border) !important;
                color: var(--psa-text-muted) !important;
                font-size: 1.08rem !important;
                font-weight: 700 !important;
                letter-spacing: 0.01em !important;
                box-shadow: 0 14px 34px rgba(8, 15, 28, 0.20) !important;
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease !important;
            }}

            [data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover {{
                transform: translateY(-1px);
                border-color: rgba(59, 130, 246, 0.30) !important;
                box-shadow: 0 20px 40px rgba(37, 99, 235, 0.16) !important;
            }}

            [data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-pressed="true"] {{
                background: linear-gradient(135deg, rgba(59, 130, 246, 0.32), rgba(59, 130, 246, 0.14)) !important;
                border-color: rgba(59, 130, 246, 0.42) !important;
                color: var(--psa-text) !important;
                box-shadow: 0 22px 44px rgba(37, 99, 235, 0.20) !important;
            }}

            [data-testid="stFileUploader"] {{
                background: rgba(15, 23, 42, 0.56);
                border: 1px dashed rgba(59, 130, 246, 0.34);
                border-radius: 22px;
                padding: 0.55rem;
            }}

            .stTextInput input,
            .stNumberInput input,
            .stTextArea textarea {{
                background: rgba(8, 15, 28, 0.82) !important;
                border: 1px solid var(--psa-border) !important;
                border-radius: 18px !important;
                color: var(--psa-text) !important;
            }}

            .stTextArea textarea {{
                min-height: 120px !important;
                line-height: 1.5 !important;
            }}

            div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button,
            div[data-testid="stFormSubmitButton"] > button {{
                border-radius: 16px;
                border: 1px solid rgba(59, 130, 246, 0.30);
                background: linear-gradient(135deg, rgba(59, 130, 246, 0.96), rgba(37, 99, 235, 0.92));
                color: #eff6ff;
                font-weight: 700;
                box-shadow: 0 16px 38px rgba(37, 99, 235, 0.22);
            }}

            div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button[kind="secondary"] {{
                background: rgba(15, 23, 42, 0.84);
                border: 1px solid var(--psa-border);
                box-shadow: none;
            }}

            [data-testid="stExpander"] {{
                border: 1px solid var(--psa-border);
                border-radius: 18px;
                background: rgba(15, 23, 42, 0.54);
                overflow: hidden;
            }}

            .psa-hero {{
                margin-bottom: 0.3rem;
            }}

            .psa-hero-title {{
                margin: 0;
                font-size: 1.85rem;
                font-weight: 700;
                letter-spacing: -0.02em;
            }}

            .psa-hero-subtitle {{
                margin-top: 0.12rem;
                color: var(--psa-text-muted);
                font-size: 0.95rem;
            }}

            .psa-hero-badge {{
                display: inline-flex;
                align-items: center;
                gap: 0.45rem;
                border-radius: 999px;
                border: 1px solid var(--psa-border);
                background: rgba(15, 23, 42, 0.74);
                padding: 0.42rem 0.78rem;
                font-size: 0.9rem;
                font-weight: 700;
                white-space: nowrap;
            }}

            .psa-card {{
                background: rgba(15, 23, 42, 0.70);
                border: 1px solid var(--psa-border);
                border-radius: 18px;
                padding: 0.78rem 0.9rem;
                box-shadow: 0 16px 34px rgba(7, 12, 22, 0.20);
                transition: transform 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
            }}

            .psa-card:hover {{
                transform: translateY(-2px);
                border-color: rgba(59, 130, 246, 0.26);
                box-shadow: 0 22px 40px rgba(37, 99, 235, 0.12);
            }}

            .psa-card-title {{
                color: var(--psa-text-muted);
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.34rem;
            }}

            .psa-card-value {{
                color: var(--psa-text);
                font-size: 1.42rem;
                font-weight: 700;
                line-height: 1.08;
            }}

            .psa-card-caption {{
                color: var(--psa-text-muted);
                font-size: 0.82rem;
                margin-top: 0.24rem;
            }}

            .psa-upload-grid, .psa-source-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                gap: 0.9rem;
            }}

            .psa-chat-thread {{
                display: flex;
                flex-direction: column;
                gap: 2rem;
                margin-bottom: 0.35rem;
            }}

            .psa-turn {{
                display: flex;
                flex-direction: column;
                gap: 1rem;
                width: 100%;
            }}

            .psa-message-row {{
                display: flex;
                width: 100%;
            }}

            .psa-message-row.user {{
                justify-content: flex-end;
            }}

            .psa-message-row.assistant {{
                justify-content: flex-start;
            }}

            .psa-bubble {{
                border-radius: 22px;
                padding: 1rem 1.1rem;
                border: 1px solid var(--psa-border);
                box-shadow: 0 18px 42px rgba(7, 12, 22, 0.18);
                width: fit-content;
                max-width: 70%;
                word-break: break-word;
            }}

            .psa-bubble.user {{
                background: linear-gradient(135deg, rgba(29, 78, 216, 0.98), rgba(30, 64, 175, 0.94));
                border-color: rgba(96, 165, 250, 0.26);
                max-width: 66%;
            }}

            .psa-bubble.assistant {{
                background: rgba(15, 23, 42, 0.84);
                max-width: 70%;
            }}

            .psa-message-role {{
                color: rgba(226, 232, 240, 0.72);
                font-size: 0.77rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.45rem;
            }}

            .psa-message-content {{
                color: var(--psa-text);
                font-size: 0.99rem;
                line-height: 1.64;
                white-space: pre-wrap;
            }}

            .psa-message-meta {{
                color: var(--psa-text-muted);
                font-size: 0.76rem;
                margin-top: 0.46rem;
                text-align: right;
            }}

            @media (max-width: 960px) {{
                .psa-bubble {{
                    max-width: 100%;
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_shell_header(
    *,
    title: str,
    subtitle: str,
    status_badge: str,
    provider_label: str,
    model_name: str,
    metrics: list[dict[str, str]],
    connected: bool = True,
) -> None:
    status_color = SUCCESS if connected else ERROR
    with st.container():
        left_col, right_col = st.columns([6.2, 1.8], vertical_alignment="top")
        with left_col:
            st.markdown(
                (
                    '<div class="psa-hero">'
                    f'<div class="psa-hero-title">{html.escape(title)}</div>'
                    f'<div class="psa-hero-subtitle">{html.escape(subtitle)}</div>'
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
        with right_col:
            st.markdown(
                (
                    '<div class="psa-hero-badge">'
                    f'<span style="color:{status_color};">&#9679;</span>'
                    f"{html.escape(status_badge)}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            st.caption(f"Provider  \n{provider_label}")
            st.caption(f"Model  \n{model_name}")

        metric_columns = st.columns(len(metrics))
        for column, card in zip(metric_columns, metrics, strict=False):
            with column:
                st.markdown(
                    f"""
                    <div class="psa-card">
                        <div class="psa-card-title">{html.escape(card.get("icon", ""))} {html.escape(card["title"])}</div>
                        <div class="psa-card-value">{html.escape(card["value"])}</div>
                        <div class="psa-card-caption">{html.escape(card["caption"])}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_message_bubble(*, role: str, content: str, timestamp: str = "") -> None:
    css_role = "user" if role == "user" else "assistant"
    role_label = "You" if role == "user" else "Assistant"
    meta_markup = (
        f'<div class="psa-message-meta">{html.escape(timestamp)}</div>' if timestamp else ""
    )
    st.markdown(
        dedent(
            f"""
            <div class="psa-message-row {css_role}">
                <div class="psa-bubble {css_role}">
                    <div class="psa-message-role">{html.escape(role_label)}</div>
                    <div class="psa-message-content">{html.escape(content)}</div>
                    {meta_markup}
                </div>
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_conversation_turn(
    *,
    user_content: str,
    assistant_content: str | None = None,
    user_timestamp: str = "",
    assistant_timestamp: str = "",
) -> None:
    user_meta = (
        f'<div class="psa-message-meta">{html.escape(user_timestamp)}</div>'
        if user_timestamp
        else ""
    )
    assistant_block = ""
    if assistant_content is not None:
        assistant_meta = (
            f'<div class="psa-message-meta">{html.escape(assistant_timestamp)}</div>'
            if assistant_timestamp
            else ""
        )
        assistant_block = dedent(
            f"""
            <div class="psa-message-row assistant">
                <div class="psa-bubble assistant">
                    <div class="psa-message-role">Product Support AI</div>
                    <div class="psa-message-content">{html.escape(assistant_content)}</div>
                    {assistant_meta}
                </div>
            </div>
            """
        ).strip()

    st.markdown(
        dedent(
            f"""
            <div class="psa-turn">
                <div class="psa-message-row user">
                    <div class="psa-bubble user">
                        <div class="psa-message-role">You</div>
                        <div class="psa-message-content">{html.escape(user_content)}</div>
                        {user_meta}
                    </div>
                </div>
                {assistant_block}
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_card_grid(cards: list[str], *, css_class: str = "psa-upload-grid") -> None:
    st.markdown(f'<div class="{css_class}">{"".join(cards)}</div>', unsafe_allow_html=True)


def build_simple_card(*, title: str, value: str, caption: str = "") -> str:
    caption_block = (
        f'<div class="psa-card-caption">{html.escape(caption)}</div>' if caption else ""
    )
    return (
        f'<div class="psa-card">'
        f'<div class="psa-card-title">{html.escape(title)}</div>'
        f'<div class="psa-card-value">{html.escape(value)}</div>'
        f"{caption_block}"
        f"</div>"
    )
