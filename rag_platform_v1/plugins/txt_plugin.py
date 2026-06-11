"""Plain text processor plugin."""
import os
from typing import List
from plugins.base_plugin import BasePlugin, DocumentChunk


class TXTPlugin(BasePlugin):
    SUPPORTED_EXTENSIONS = [".txt", ".log"]

    def extract(self, file_path: str) -> List[DocumentChunk]:
        if not self.validate_file(file_path):
            return []

        chunks: List[DocumentChunk] = []
        source = os.path.basename(file_path)

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()

            if content:
                # Split into paragraphs by double newlines
                paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                for para in paragraphs:
                    chunks.append(DocumentChunk(
                        text=para,
                        source=source,
                        page=0,
                        section="",
                        chunk_type="text",
                    ))

        except Exception as e:
            chunks.append(DocumentChunk(
                text=f"[ERROR extracting TXT: {e}]",
                source=source,
                page=0,
                chunk_type="error",
            ))

        return chunks
