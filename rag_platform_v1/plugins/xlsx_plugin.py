"""XLSX processor plugin - handles multiple sheets."""
import os
from typing import List
from plugins.base_plugin import BasePlugin, DocumentChunk


class XLSXPlugin(BasePlugin):
    SUPPORTED_EXTENSIONS = [".xlsx", ".xls"]

    def extract(self, file_path: str) -> List[DocumentChunk]:
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas not installed. Run: pip install pandas openpyxl")

        if not self.validate_file(file_path):
            return []

        chunks: List[DocumentChunk] = []
        source = os.path.basename(file_path)

        try:
            xl = pd.ExcelFile(file_path)
            sheet_names = xl.sheet_names

            for sheet_name in sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                df = df.fillna("")
                headers = list(df.columns)

                # Schema chunk per sheet
                schema_text = (
                    f"Sheet '{sheet_name}' in {source}:\n"
                    f"Columns: {', '.join(str(h) for h in headers)}\n"
                    f"Rows: {len(df)}"
                )
                chunks.append(DocumentChunk(
                    text=schema_text,
                    source=source,
                    page=0,
                    section=f"Sheet: {sheet_name}",
                    chunk_type="table",
                    metadata={"sheet": sheet_name, "headers": headers},
                ))

                # Row-level chunks
                for idx, row in df.iterrows():
                    parts = [f"{col}: {row[col]}" for col in headers if str(row[col]).strip()]
                    row_text = " | ".join(parts)
                    if row_text.strip():
                        chunks.append(DocumentChunk(
                            text=row_text,
                            source=source,
                            page=0,
                            section=f"Sheet: {sheet_name}",
                            chunk_type="table",
                            metadata={"sheet": sheet_name, "row_index": idx, "headers": headers},
                        ))

        except Exception as e:
            chunks.append(DocumentChunk(
                text=f"[ERROR extracting XLSX: {e}]",
                source=source,
                page=0,
                chunk_type="error",
            ))

        return chunks
