from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from product_support_agent.config import Settings
from product_support_agent.logger import get_logger
from product_support_agent.models import ChunkMetadata, ChunkRecord, ExtractedDocument, ServiceStatus
from product_support_agent.utils import utc_timestamp


@dataclass(slots=True)
class _SemanticBlock:
    text: str
    section_title: str | None
    is_table: bool = False


class ChunkingService:
    """Splits extracted text into metadata-rich chunks while preserving structure."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = get_logger(__name__)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.app.chunk_size,
            chunk_overlap=settings.app.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    @property
    def chunk_size(self) -> int:
        return self._settings.app.chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._settings.app.chunk_overlap

    def chunk_documents(self, documents: list[ExtractedDocument]) -> list[ChunkRecord]:
        chunk_records: list[ChunkRecord] = []
        for document in documents:
            text_chunks = self._build_document_chunks(document)
            self._logger.info(
                "Chunking extracted document: file=%s document_type=%s produced_chunks=%s",
                document.file_name,
                document.document_type,
                len(text_chunks),
            )
            for chunk_number, block in enumerate(text_chunks, start=1):
                chunk_records.append(
                    ChunkRecord(
                        chunk_id=self._build_chunk_id(document, chunk_number),
                        text=block.text,
                        metadata=ChunkMetadata(
                            file_name=document.file_name,
                            document_type=document.document_type,
                            chunk_number=chunk_number,
                            page_number=document.page_number,
                            row_number=document.row_number,
                            section_title=block.section_title,
                            source_path=document.source_path,
                            timestamp=utc_timestamp(),
                        ),
                    )
                )
        self._logger.info("Chunk generation completed: total_chunks=%s", len(chunk_records))
        return chunk_records

    def _build_chunk_id(self, document: ExtractedDocument, chunk_number: int) -> str:
        page_part = document.page_number if document.page_number is not None else "na"
        row_part = document.row_number if document.row_number is not None else "na"
        return f"{document.file_name}:{page_part}:{row_part}:{chunk_number}"

    def _build_document_chunks(self, document: ExtractedDocument) -> list[_SemanticBlock]:
        semantic_blocks = self._build_semantic_blocks(document)
        if not semantic_blocks:
            fallback_text = document.text.strip()
            return [
                _SemanticBlock(text=text_chunk, section_title=None)
                for text_chunk in self._splitter.split_text(fallback_text)
                if text_chunk.strip()
            ]

        chunks: list[_SemanticBlock] = []
        current_blocks: list[_SemanticBlock] = []

        for block in semantic_blocks:
            if len(block.text) > self.chunk_size:
                if current_blocks:
                    chunks.append(self._combine_blocks(current_blocks))
                    current_blocks = []
                chunks.extend(self._split_large_block(block))
                continue

            if current_blocks and current_blocks[-1].is_table and block.is_table:
                chunks.append(self._combine_blocks(current_blocks))
                current_blocks = [block]
                continue

            if current_blocks and current_blocks[-1].is_table != block.is_table:
                chunks.append(self._combine_blocks(current_blocks))
                current_blocks = [block]
                continue

            prospective_blocks = [*current_blocks, block]
            if current_blocks and len(self._join_block_texts(prospective_blocks)) > self.chunk_size:
                chunks.append(self._combine_blocks(current_blocks))
                overlap_blocks = self._select_overlap_blocks(current_blocks)
                current_blocks = [*overlap_blocks, block]
                if len(self._join_block_texts(current_blocks)) > self.chunk_size:
                    chunks.append(self._combine_blocks([block]))
                    current_blocks = []
                continue

            current_blocks = prospective_blocks

        if current_blocks:
            chunks.append(self._combine_blocks(current_blocks))

        return chunks

    def _build_semantic_blocks(self, document: ExtractedDocument) -> list[_SemanticBlock]:
        lines = [line.rstrip() for line in document.text.splitlines()]
        blocks: list[_SemanticBlock] = []
        current_lines: list[str] = []
        current_kind: str | None = None
        current_section_title: str | None = None

        def flush_current_block() -> None:
            nonlocal current_lines, current_kind
            if not current_lines:
                return
            block_text = self._merge_block_lines(current_lines, current_kind or "prose")
            if block_text:
                blocks.append(
                    _SemanticBlock(
                        text=block_text,
                        section_title=current_section_title,
                        is_table=current_kind == "table",
                    )
                )
            current_lines = []
            current_kind = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                flush_current_block()
                continue

            if self._looks_like_heading(line):
                flush_current_block()
                current_section_title = line.rstrip(":").strip() or current_section_title
                continue

            line_kind = self._classify_line(line)
            if not current_lines:
                current_lines = [line]
                current_kind = line_kind
                continue

            if current_kind == "table" and line_kind == "table":
                current_lines.append(line)
                continue

            if current_kind == "bullet" and line_kind == "prose":
                current_lines.append(line)
                continue

            if current_kind == line_kind and line_kind == "prose":
                current_lines.append(line)
                continue

            flush_current_block()
            current_lines = [line]
            current_kind = line_kind

        flush_current_block()
        return blocks

    @staticmethod
    def _classify_line(line: str) -> str:
        if " | " in line:
            return "table"
        if line.startswith("\u2022") or line.startswith("- "):
            return "bullet"
        return "prose"

    @staticmethod
    def _looks_like_heading(line: str) -> bool:
        if line.startswith("\u2022") or " | " in line:
            return False

        if line.endswith(":") and len(line) <= 120:
            return True

        alpha_characters = [character for character in line if character.isalpha()]
        if not alpha_characters:
            return False

        uppercase_ratio = sum(character.isupper() for character in alpha_characters) / len(
            alpha_characters
        )
        return uppercase_ratio >= 0.75 and len(line.split()) <= 8

    @staticmethod
    def _merge_block_lines(lines: list[str], kind: str) -> str:
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        if not cleaned_lines:
            return ""
        if kind == "table":
            return "\n".join(ChunkingService._merge_table_continuations(cleaned_lines))
        return " ".join(cleaned_lines)

    @staticmethod
    def _merge_table_continuations(lines: list[str]) -> list[str]:
        merged_lines: list[str] = []
        for line in lines:
            if " | " in line or not merged_lines:
                merged_lines.append(line)
                continue

            previous_line = merged_lines.pop()
            previous_parts = previous_line.split(" | ")
            if previous_parts and (
                previous_parts[-1].endswith("(")
                or previous_parts[-1].endswith("(In")
                or previous_parts[-1].count("(") > previous_parts[-1].count(")")
            ):
                previous_parts[-1] = f"{previous_parts[-1]} {line}".strip()
            else:
                previous_parts[0] = f"{previous_parts[0]} {line}".strip()
            merged_lines.append(" | ".join(previous_parts))
        return merged_lines

    def _split_large_block(self, block: _SemanticBlock) -> list[_SemanticBlock]:
        return [
            _SemanticBlock(
                text=text_chunk,
                section_title=block.section_title,
                is_table=block.is_table,
            )
            for text_chunk in self._splitter.split_text(block.text)
            if text_chunk.strip()
        ]

    def _combine_blocks(self, blocks: list[_SemanticBlock]) -> _SemanticBlock:
        section_title = next((block.section_title for block in blocks if block.section_title), None)
        return _SemanticBlock(
            text=self._join_block_texts(blocks),
            section_title=section_title,
            is_table=all(block.is_table for block in blocks),
        )

    @staticmethod
    def _join_block_texts(blocks: list[_SemanticBlock]) -> str:
        return "\n\n".join(block.text for block in blocks if block.text.strip()).strip()

    def _select_overlap_blocks(self, blocks: list[_SemanticBlock]) -> list[_SemanticBlock]:
        if self.chunk_overlap <= 0:
            return []

        selected_blocks: list[_SemanticBlock] = []
        current_length = 0
        for block in reversed(blocks):
            if block.is_table:
                break
            prospective_length = current_length + len(block.text)
            if selected_blocks and prospective_length > self.chunk_overlap:
                break
            selected_blocks.insert(0, block)
            current_length = prospective_length
        return selected_blocks

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            name="chunking",
            state="ready",
            details=(
                f"Recursive chunking is configured with chunk_size={self.chunk_size} "
                f"and chunk_overlap={self.chunk_overlap}."
            ),
        )
