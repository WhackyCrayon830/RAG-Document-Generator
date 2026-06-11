"""PDF processor plugin using PyMuPDF (fitz)."""
import os
from typing import List
from plugins.base_plugin import BasePlugin, DocumentChunk


class PDFPlugin(BasePlugin):
    SUPPORTED_EXTENSIONS = [".pdf"]

    def extract(self, file_path: str) -> List[DocumentChunk]:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")

        if not self.validate_file(file_path):
            return []

        chunks: List[DocumentChunk] = []
        source = os.path.basename(file_path)
        current_section = ""

        try:
            doc = fitz.open(file_path)
            for page_num, page in enumerate(doc, start=1):
                # Extract text blocks with layout preservation
                blocks = page.get_text("dict")["blocks"]
                page_text_parts = []

                for block in blocks:
                    if block.get("type") == 0:  # Text block
                        for line in block.get("lines", []):
                            line_text = " ".join(
                                span["text"] for span in line.get("spans", [])
                            ).strip()
                            if not line_text:
                                continue

                            # Detect headings by font size
                            spans = line.get("spans", [])
                            if spans:
                                avg_size = sum(s["size"] for s in spans) / len(spans)
                                if avg_size > 14:
                                    current_section = line_text
                                    chunks.append(DocumentChunk(
                                        text=line_text,
                                        source=source,
                                        page=page_num,
                                        section=current_section,
                                        chunk_type="heading",
                                    ))
                                    continue

                            page_text_parts.append(line_text)

                    elif block.get("type") == 1:  # Image block - skip for now
                        pass

                # Try table extraction
                try:
                    tables = page.find_tables()
                    for table in tables.tables:
                        rows = table.extract()
                        if not rows:
                            continue
                        headers = rows[0] if rows else []
                        table_lines = [" | ".join(str(c) for c in headers)]
                        table_lines.append("-" * 40)
                        for row in rows[1:]:
                            table_lines.append(" | ".join(str(c) for c in row))
                        table_text = "\n".join(table_lines)
                        chunks.append(DocumentChunk(
                            text=table_text,
                            source=source,
                            page=page_num,
                            section=current_section,
                            chunk_type="table",
                            metadata={"headers": headers},
                        ))
                except Exception:
                    pass  # Table extraction is best-effort

                # Add page text as a single chunk
                full_page_text = "\n".join(page_text_parts).strip()
                if full_page_text:
                    chunks.append(DocumentChunk(
                        text=full_page_text,
                        source=source,
                        page=page_num,
                        section=current_section,
                        chunk_type="text",
                    ))

            doc.close()
        except Exception as e:
            chunks.append(DocumentChunk(
                text=f"[ERROR extracting PDF: {e}]",
                source=source,
                page=0,
                chunk_type="error",
            ))

        return chunks
