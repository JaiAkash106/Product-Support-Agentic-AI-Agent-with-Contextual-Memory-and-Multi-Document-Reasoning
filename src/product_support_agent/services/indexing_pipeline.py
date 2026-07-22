from __future__ import annotations

from product_support_agent.config import Settings
from product_support_agent.exceptions import IngestionPipelineError, ValidationError
from product_support_agent.logger import get_logger
from product_support_agent.models import IndexBuildResult, UploadPayload
from product_support_agent.services.chunking import ChunkingService
from product_support_agent.services.document_loader import DocumentLoader
from product_support_agent.services.embedding_service import EmbeddingService
from product_support_agent.services.metadata_manager import MetadataManager
from product_support_agent.services.upload_manager import UploadManager
from product_support_agent.services.vector_store import VectorStoreService


class KnowledgeBaseIngestionPipeline:
    """Coordinates upload, extraction, chunking, embeddings, and FAISS persistence."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = get_logger(__name__)
        self._metadata_manager = MetadataManager(settings)
        self._upload_manager = UploadManager(settings)
        self._document_loader = DocumentLoader()
        self._chunking_service = ChunkingService(settings)
        self._embedding_service = EmbeddingService(settings)
        self._vector_store = VectorStoreService(settings, self._metadata_manager)

    def ingest_uploads(self, payloads: list[UploadPayload]) -> IndexBuildResult:
        if not payloads:
            raise ValidationError("No files were provided for ingestion.")

        self._metadata_manager.ensure_storage_files()
        uploaded_files = self._upload_manager.save_files(payloads)
        processed_uploads = [
            upload_result
            for upload_result in uploaded_files
            if upload_result.status == "processed"
        ]
        duplicate_uploads = [
            upload_result
            for upload_result in uploaded_files
            if upload_result.status == "duplicate_skipped"
        ]

        self._metadata_manager.record_uploads(processed_uploads)

        if not processed_uploads:
            duplicate_messages = [
                upload_result.status_message for upload_result in duplicate_uploads
            ]
            return IndexBuildResult(
                uploaded_files=0,
                extracted_documents=0,
                chunks_created=0,
                vectors_in_index=self._vector_store.current_vector_count(),
                index_file=self._settings.paths.vector_index_file,
                metadata_file=self._settings.paths.vector_metadata_file,
                failed_files=[],
                duplicate_files=[
                    upload_result.original_file_name for upload_result in duplicate_uploads
                ],
                duplicate_messages=duplicate_messages,
            )

        extracted_documents, failed_files = self._document_loader.load_files(
            [
                result.stored_path
                for result in processed_uploads
                if result.stored_path is not None
            ]
        )
        if failed_files:
            self._logger.warning("Some files failed during extraction: %s", failed_files)
        if not extracted_documents:
            raise IngestionPipelineError(
                "All uploaded files failed during text extraction. "
                f"Failures: {failed_files}"
            )

        chunk_records = self._chunking_service.chunk_documents(extracted_documents)
        if not chunk_records:
            raise IngestionPipelineError("Chunk generation produced no usable output.")

        embeddings = self._embedding_service.embed_texts(
            [chunk_record.text for chunk_record in chunk_records]
        )
        vectors_in_index = self._vector_store.add_embeddings(chunk_records, embeddings)

        self._logger.info(
            "Knowledge base ingestion completed: uploads=%s extracted=%s chunks=%s total_vectors=%s",
            len(processed_uploads),
            len(extracted_documents),
            len(chunk_records),
            vectors_in_index,
        )
        return IndexBuildResult(
            uploaded_files=len(processed_uploads),
            extracted_documents=len(extracted_documents),
            chunks_created=len(chunk_records),
            vectors_in_index=vectors_in_index,
            index_file=self._settings.paths.vector_index_file,
            metadata_file=self._settings.paths.vector_metadata_file,
            failed_files=failed_files,
            duplicate_files=[
                upload_result.original_file_name for upload_result in duplicate_uploads
            ],
            duplicate_messages=[
                upload_result.status_message for upload_result in duplicate_uploads
            ],
        )
