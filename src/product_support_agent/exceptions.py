from __future__ import annotations


class ProductSupportAgentError(Exception):
    """Base exception for the product support agent project."""


class ValidationError(ProductSupportAgentError):
    """Raised when uploaded or loaded content fails validation."""


class ExtractionError(ProductSupportAgentError):
    """Raised when a source file cannot be converted into usable text."""


class EmbeddingError(ProductSupportAgentError):
    """Raised when embeddings cannot be generated."""


class ConfigurationError(ProductSupportAgentError):
    """Raised when a required runtime configuration value is missing or invalid."""


class GenerationError(ProductSupportAgentError):
    """Raised when grounded answer generation fails."""


class ContextualizationError(ProductSupportAgentError):
    """Raised when a follow-up query cannot be resolved into a standalone query."""


class IndexPersistenceError(ProductSupportAgentError):
    """Raised when the FAISS index cannot be created, loaded, or saved."""


class MetadataError(ProductSupportAgentError):
    """Raised when metadata persistence fails."""


class IngestionPipelineError(ProductSupportAgentError):
    """Raised when the end-to-end ingestion pipeline fails."""
