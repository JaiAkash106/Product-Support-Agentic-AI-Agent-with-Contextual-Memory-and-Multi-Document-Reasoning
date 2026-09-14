from __future__ import annotations

from dataclasses import replace

from product_support_agent.models import ExtractedDocument
from product_support_agent.services.chunking import ChunkingService


def test_chunking_service_preserves_metadata(test_settings) -> None:
    document = ExtractedDocument(
        file_name="guide.txt",
        document_type="txt",
        source_path=test_settings.paths.upload_dir / "guide.txt",
        text="A" * 70 + "\n" + "B" * 70,
        page_number=None,
        row_number=None,
    )

    chunks = ChunkingService(test_settings).chunk_documents([document])

    assert len(chunks) >= 2
    assert chunks[0].metadata.file_name == "guide.txt"
    assert chunks[0].metadata.document_type == "txt"
    assert chunks[0].metadata.chunk_number == 1


def test_chunking_service_keeps_table_rows_and_section_titles_together(test_settings) -> None:
    tuned_settings = replace(
        test_settings,
        app=replace(test_settings.app, chunk_size=220, chunk_overlap=0),
    )
    document = ExtractedDocument(
        file_name="instructions.pdf",
        document_type="pdf",
        source_path=test_settings.paths.upload_dir / "instructions.pdf",
        page_number=2,
        text=(
            "ADVANCED CODING (GUIDELINES):\n\n"
            "Programming Language | Version\n"
            "Python | 3.8.0\n"
            "Java | 1.8.0_171\n\n"
            "\u2022 There are two hands-on coding questions.\n"
        ),
    )

    chunks = ChunkingService(tuned_settings).chunk_documents([document])

    assert len(chunks) == 2
    table_chunk = chunks[0]
    assert "Programming Language | Version" in table_chunk.text
    assert "Python | 3.8.0" in table_chunk.text
    assert table_chunk.metadata.section_title == "ADVANCED CODING (GUIDELINES)"
    assert table_chunk.metadata.page_number == 2


def test_chunking_service_treats_pipe_delimited_chapter_headers_as_section_titles(
    test_settings,
) -> None:
    tuned_settings = replace(
        test_settings,
        app=replace(test_settings.app, chunk_size=320, chunk_overlap=0),
    )
    document = ExtractedDocument(
        file_name="deep-learning.pdf",
        document_type="pdf",
        source_path=test_settings.paths.upload_dir / "deep-learning.pdf",
        page_number=731,
        text=(
            "CHAPTER | 20. | DEEP | GENERATIVE | MODELS\n"
            "Generative models can provide answers to inference problems.\n"
            "They also learn hierarchical representations of the world.\n"
        ),
    )

    chunks = ChunkingService(tuned_settings).chunk_documents([document])

    assert len(chunks) == 1
    assert chunks[0].metadata.section_title == "CHAPTER 20. DEEP GENERATIVE MODELS"
    assert "CHAPTER | 20." not in chunks[0].text
    assert "Generative models can provide answers" in chunks[0].text
