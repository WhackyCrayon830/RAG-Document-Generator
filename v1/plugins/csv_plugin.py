"""CSV processor plugin - converts tables into retrieval-friendly text."""
import os
from typing import List
from plugins.base_plugin import BasePlugin, DocumentChunk


class CSVPlugin(BasePlugin):
    SUPPORTED_EXTENSIONS = [".csv"]

    def extract(self, file_path: str) -> List[DocumentChunk]:
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas not installed. Run: pip install pandas")

        if not self.validate_file(file_path):
            return []

        chunks: List[DocumentChunk] = []
        source = os.path.basename(file_path)

        try:
            df = pd.read_csv(file_path)
            df = df.fillna("")
            headers = list(df.columns)

            # Schema metadata chunk
            schema_text = f"Table schema for {source}:\nColumns: {', '.join(headers)}\nRows: {len(df)}"
            chunks.append(DocumentChunk(
                text=schema_text,
                source=source,
                page=0,
                section="Schema",
                chunk_type="table",
                metadata={"headers": headers, "row_count": len(df)},
            ))

            # Convert each row to readable text
            for idx, row in df.iterrows():
                parts = [f"{col}: {row[col]}" for col in headers if str(row[col]).strip()]
                row_text = " | ".join(parts)
                if row_text.strip():
                    chunks.append(DocumentChunk(
                        text=row_text,
                        source=source,
                        page=0,
                        section="Data",
                        chunk_type="table",
                        metadata={"row_index": idx, "headers": headers},
                    ))

            # Also add a full markdown table preview (first 50 rows)
            preview = df.head(50).to_markdown(index=False) if hasattr(df, "to_markdown") else df.head(50).to_string()
            if preview:
                chunks.append(DocumentChunk(
                    text=f"Table preview:\n{preview}",
                    source=source,
                    page=0,
                    section="Preview",
                    chunk_type="table",
                    metadata={"headers": headers},
                ))

        except Exception as e:
            chunks.append(DocumentChunk(
                text=f"[ERROR extracting CSV: {e}]",
                source=source,
                page=0,
                chunk_type="error",
            ))

        return chunks
