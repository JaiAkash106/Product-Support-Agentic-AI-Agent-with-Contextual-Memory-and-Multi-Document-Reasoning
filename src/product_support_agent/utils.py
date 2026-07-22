from __future__ import annotations

from datetime import UTC, datetime


def format_supported_extensions(extensions: tuple[str, ...]) -> str:
    return ", ".join(extension.upper().replace(".", "") for extension in extensions)


def human_readable_size(size_in_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_in_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_in_bytes} B"


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
