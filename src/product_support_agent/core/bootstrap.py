from __future__ import annotations

from product_support_agent.config import Settings, ensure_runtime_directories
from product_support_agent.logger import configure_logging, get_logger
from product_support_agent.services.metadata_manager import MetadataManager


def bootstrap_application(settings: Settings) -> None:
    ensure_runtime_directories(settings)
    configure_logging(settings)

    logger = get_logger(__name__)
    MetadataManager(settings).ensure_storage_files()
    logger.info(
        "Application bootstrap completed for environment=%s",
        settings.app.environment,
    )
