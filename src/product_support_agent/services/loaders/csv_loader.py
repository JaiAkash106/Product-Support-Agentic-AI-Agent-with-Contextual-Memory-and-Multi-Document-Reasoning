from __future__ import annotations

from pathlib import Path

import pandas as pd

from product_support_agent.exceptions import ExtractionError
from product_support_agent.models import ExtractedDocument
from product_support_agent.services.loaders.base import BaseDocumentLoader


class CSVDocumentLoader(BaseDocumentLoader):
    """Extracts row-level text from CSV files for structured grounding."""

    supported_extension = ".csv"
    document_type = "csv"

    def load(self, file_path: Path) -> list[ExtractedDocument]:
        try:
            dataframe = pd.read_csv(file_path, dtype=str).fillna("")
        except Exception as exc:  # pragma: no cover - pandas parsing failure path
            raise ExtractionError(f"Unable to parse CSV file: {file_path.name}") from exc

        if dataframe.empty:
            raise ExtractionError(f"CSV file {file_path.name} is empty.")

        extracted_rows: list[ExtractedDocument] = []
        for row_number, row in enumerate(
            dataframe.to_dict(orient="records"), start=1
        ):
            row_text_parts = [
                f"{column}: {str(value).strip()}"
                for column, value in row.items()
                if str(value).strip()
            ]
            row_text = " | ".join(row_text_parts).strip()
            if not row_text:
                continue

            extracted_rows.append(
                ExtractedDocument(
                    file_name=file_path.name,
                    document_type=self.document_type,
                    source_path=file_path,
                    text=row_text,
                    row_number=row_number,
                )
            )

        if not extracted_rows:
            raise ExtractionError(
                f"CSV file {file_path.name} does not contain any non-empty rows."
            )

        return extracted_rows
