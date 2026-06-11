"""Markdown processor plugin - preserves headings and fenced code blocks."""
import os
import re
from typing import List
from plugins.base_plugin import BasePlugin, DocumentChunk


class MarkdownPlugin(BasePlugin):
    SUPPORTED_EXTENSIONS = [".md", ".markdown"]

    def extract(self, file_path: str) -> List[DocumentChunk]:
        if not self.validate_file(file_path):
            return []

        chunks: List[DocumentChunk] = []
        source = os.path.basename(file_path)
        current_section = ""

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            lines = content.split("\n")
            buffer: List[str] = []
            in_code_block = False
            code_buffer: List[str] = []
            code_lang = ""

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

            for line in lines:
                # Detect fenced code blocks
                fence_match = re.match(r"^```(\w*)", line)
                if fence_match and not in_code_block:
                    flush_buffer()
                    in_code_block = True
                    code_lang = fence_match.group(1)
                    code_buffer = [line]
                    continue
                elif line.strip() == "```" and in_code_block:
                    code_buffer.append(line)
                    in_code_block = False
                    chunks.append(DocumentChunk(
                        text="\n".join(code_buffer),
                        source=source,
                        page=0,
                        section=current_section,
                        chunk_type="code",
                        metadata={"language": code_lang},
                    ))
                    code_buffer = []
                    continue

                if in_code_block:
                    code_buffer.append(line)
                    continue

                # Detect headings
                heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
                if heading_match:
                    flush_buffer()
                    current_section = heading_match.group(2).strip()
                    chunks.append(DocumentChunk(
                        text=line.strip(),
                        source=source,
                        page=0,
                        section=current_section,
                        chunk_type="heading",
                        metadata={"level": len(heading_match.group(1))},
                    ))
                else:
                    buffer.append(line)

            flush_buffer()

        except Exception as e:
            chunks.append(DocumentChunk(
                text=f"[ERROR extracting Markdown: {e}]",
                source=source,
                page=0,
                chunk_type="error",
            ))

        return chunks
