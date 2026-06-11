"""HTML processor plugin - strips irrelevant tags, preserves semantic structure."""
import os
import re
from typing import List
from plugins.base_plugin import BasePlugin, DocumentChunk


class HTMLPlugin(BasePlugin):
    SUPPORTED_EXTENSIONS = [".html", ".htm"]

    def extract(self, file_path: str) -> List[DocumentChunk]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("beautifulsoup4 not installed. Run: pip install beautifulsoup4")

        if not self.validate_file(file_path):
            return []

        chunks: List[DocumentChunk] = []
        source = os.path.basename(file_path)
        current_section = ""

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()

            soup = BeautifulSoup(raw, "html.parser")

            # Remove scripts, styles, nav, footer
            for tag in soup(["script", "style", "nav", "footer", "head", "noscript"]):
                tag.decompose()

            # Process headings and paragraphs in order
            buffer: List[str] = []

            def flush_buffer():
                text = "\n".join(buffer).strip()
                if text:
                    chunks.append(DocumentChunk(
                        text=text,
                        source=source,
                        page=0,
                        section=current_section,
                        chunk_type="text",
                    ))
                buffer.clear()

            for elem in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "pre", "code"]):
                text = elem.get_text(separator=" ", strip=True)
                if not text:
                    continue

                tag = elem.name
                if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    flush_buffer()
                    current_section = text
                    chunks.append(DocumentChunk(
                        text=text,
                        source=source,
                        page=0,
                        section=current_section,
                        chunk_type="heading",
                        metadata={"tag": tag},
                    ))
                elif tag in ["pre", "code"]:
                    flush_buffer()
                    chunks.append(DocumentChunk(
                        text=text,
                        source=source,
                        page=0,
                        section=current_section,
                        chunk_type="code",
                    ))
                else:
                    buffer.append(text)

            flush_buffer()

        except Exception as e:
            chunks.append(DocumentChunk(
                text=f"[ERROR extracting HTML: {e}]",
                source=source,
                page=0,
                chunk_type="error",
            ))

        return chunks
