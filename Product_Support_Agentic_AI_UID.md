# Product Support Agentic AI Agent with Contextual Memory and Multi-Document Reasoning
## User Interface Design (UID)

## Title Page

| Field | Value |
|---|---|
| Document Title | Product Support Agentic AI Agent with Contextual Memory and Multi-Document Reasoning - UID |
| Document ID | HCL-PSAAI-UID-001 |
| Version | 1.1 |
| Date | 2026-08-19 |
| Author | Codex Documentation Review |
| Company | HCL |
| Source Document | `Product_Support_Agentic_AI_Enterprise_Documentation.docx` |

## Revision History

| Version No | Date | Prepared by / Modified by | Significant Changes |
|---|---|---|---|
| 1.0 | 2026-06-13 | Senior UX Architect | Initial User Interface Design specification and Streamlit layout blueprint |
| 1.1 | 2026-08-19 | Codex Documentation Review | Reviewed and aligned the UID to the current Streamlit interface and interaction behavior |

## Table of Contents

1. Overview  
2. User Personas and Primary Tasks  
3. Information Architecture  
4. Visual Design System  
5. Ask AI Experience  
6. Ingestion Experience  
7. Sidebar and Developer Tools  
8. Feedback, Error States, and Empty States  
9. Accessibility and Responsiveness  
10. Documentation Consistency Notes  
11. References  

## 1. Overview

This document describes the current user interface and user interaction behavior of the Streamlit application. It reflects the implemented UI in the repository rather than earlier prototype concepts.

## 2. User Personas and Primary Tasks

### 2.1 Support User

- asks grounded questions about uploaded documents
- reviews assistant answers and citations
- continues a follow-up conversation in the same session

### 2.2 Knowledge Administrator

- uploads supported files
- builds the knowledge base
- reviews indexed document cards
- clears the knowledge base when needed

### 2.3 Developer / Reviewer

- inspects retrieval details
- checks source citations and metadata
- reviews debug information from the latest answer

## 3. Information Architecture

### 3.1 Primary Navigation

The current UI exposes two primary top-level destinations through a segmented control:

- `Ask AI`
- `Ingestion`

### 3.2 Persistent Sidebar

The sidebar is always visible and contains:

- product title
- workspace summary
- AI status
- conversation controls
- developer tools

### 3.3 Main Content Zones

The main area contains:

1. shell header
2. summary metric cards
3. primary navigation
4. current page content (`Ask AI` or `Ingestion`)

## 4. Visual Design System

### 4.1 Theme

The implemented UI uses a dark enterprise theme with:

- deep blue/black background gradients
- blue accent color
- soft green connected-state accents
- rounded cards and rounded message bubbles
- subdued borders and shadows

### 4.2 Typography and Layout Style

The current design emphasizes:

- large product heading
- compact metrics
- high-contrast content surfaces
- wide chat workspace
- separated developer details outside the main chat stream

### 4.3 Message Presentation

Conversation messages are rendered as custom HTML/CSS bubbles through Streamlit markdown:

- user messages are right-aligned
- assistant messages are left-aligned
- timestamps appear inside bubbles when available

## 5. Ask AI Experience

### 5.1 Primary Goal

The `Ask AI` view is the main usage path and is designed to keep the conversation visually clean.

### 5.2 Screen Elements

The current `Ask AI` experience includes:

- a bordered conversation container
- an empty-state guidance message when no conversation exists
- a text area for question entry
- a primary `Send` button

### 5.3 Conversation Behavior

The rendered conversation follows this vertical order:

`User question -> Assistant answer -> Next user question -> Next assistant answer`

The current implementation stores a UI transcript in Streamlit session state so previous turns can be re-rendered immediately.

### 5.4 Search Depth

Search depth is controlled from the sidebar through a slider labeled `Search Depth` with a range of `1` to `20`.

### 5.5 Grounded Answer UX

The assistant does not present itself as a general-purpose chat model. The user-facing expectation is:

- answers come from uploaded documents
- citations are attached to the latest interaction through developer tools
- insufficient evidence produces a safe fallback instead of an invented answer

## 6. Ingestion Experience

### 6.1 Upload Workflow

The `Ingestion` page includes:

- a `Choose files` uploader
- support for multiple files at once
- pre-ingestion cards for pending uploads
- a `Build Knowledge Base` primary action
- a `Clear Knowledge Base` secondary action

### 6.2 Knowledge Base Summary

After a successful ingestion run, the page shows summary cards for:

- uploaded files
- extracted documents
- chunks created
- vectors in index

### 6.3 Indexed Document Presentation

Indexed files are shown as reusable cards under `Knowledge Base`, with:

- document icon by type
- stored file name
- file size
- indexed caption with chunk count

## 7. Sidebar and Developer Tools

### 7.1 Workspace Section

The sidebar workspace section shows:

- `Documents`
- `Chunks`
- `Last Updated`

### 7.2 AI Status Section

The sidebar AI status section shows:

- provider label
- model name
- connection status

The current local environment resolves to an `Ollama` provider with model `qwen3:8b`, while the code can also support `Gemini`.

### 7.3 Conversation Section

The sidebar conversation section shows:

- assistant turn count
- search depth slider
- clear conversation button

### 7.4 Developer Tools Section

Developer tools are intentionally collapsed behind a sidebar expander and include the latest interaction's:

- sources
- debug information
- retrieval details
- metadata snapshot

This keeps technical details out of the primary chat flow.

## 8. Feedback, Error States, and Empty States

### 8.1 Empty States

Implemented empty states include:

- no conversation yet
- no latest answer details in developer tools
- no sources available for the latest answer
- no retrieval details available

### 8.2 Success Feedback

Implemented success feedback includes:

- knowledge base update success
- knowledge base clear success

### 8.3 Error and Warning Feedback

Implemented user-facing error/warning patterns include:

- warning when building without selecting files
- ingestion errors displayed through Streamlit alerts
- provider or retrieval errors surfaced through assistant response state and debug details

### 8.4 Fallback Messaging

When grounded generation cannot proceed because evidence is insufficient, the UI presents the system fallback response returned by the backend rather than a speculative answer.

## 9. Accessibility and Responsiveness

### 9.1 Accessibility

The UI uses:

- visible headings and labels
- strong text/background contrast
- button and form semantics provided by Streamlit

Formal WCAG audit results are not present in the repository and are therefore unspecified.

### 9.2 Responsiveness

The custom theme includes layout behavior for narrower screens, including:

- card wrapping
- bubble width adjustments
- preserved sidebar layout behavior through Streamlit

Detailed mobile usability validation is not documented in the repository and is therefore unspecified.

## 10. Documentation Consistency Notes

- This reviewed UID reflects the current premium dark Streamlit interface rather than the older three-mode prototype (`Support Assistant`, `Ingest Manager`, `System Settings`).
- Prompt editing, `Top-P`, and `Top-K` runtime controls are not exposed in the current UI and are therefore not described as active interface features.
- Developer details are shown in a single sidebar `Developer Tools` section rather than interrupting the conversation after every answer.
- The current UX is grounded-document-first; it does not instruct users that the assistant may answer from general training memory.

## 11. References

1. [layout.py](file:///D:/hcl/src/product_support_agent/ui/layout.py)
2. [sections.py](file:///D:/hcl/src/product_support_agent/ui/sections.py)
3. [sidebar.py](file:///D:/hcl/src/product_support_agent/ui/sidebar.py)
4. [theme.py](file:///D:/hcl/src/product_support_agent/ui/theme.py)
5. [presenter.py](file:///D:/hcl/src/product_support_agent/ui/presenter.py)
