from __future__ import annotations

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
