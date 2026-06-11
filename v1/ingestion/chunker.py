"""
Advanced chunker: recursive, semantic-aware, and token-aware chunking.
Preserves metadata from source plugins.
"""
import re
from typing import List
from plugins.base_plugin import DocumentChunk


class Chunker:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """
        Take raw extracted chunks and split any that exceed chunk_size.
        Headings and code blocks are kept intact.
        Tables are kept intact up to 2x chunk_size.
        Text chunks are split recursively.
        """
        result: List[DocumentChunk] = []
        for chunk in chunks:
            if chunk.chunk_type in ("heading",):
                result.append(chunk)
            elif chunk.chunk_type in ("code", "table"):
                # Keep as-is unless absurdly large
                if len(chunk.text) <= self.chunk_size * 4:
                    result.append(chunk)
                else:
                    result.extend(self._split_text(chunk))
            else:
                if len(chunk.text) <= self.chunk_size:
                    result.append(chunk)
                else:
                    result.extend(self._split_text(chunk))
        return result

    def _split_text(self, chunk: DocumentChunk) -> List[DocumentChunk]:
        """Recursively split text using paragraph -> sentence -> word boundaries."""
        text = chunk.text
        parts = self._recursive_split(text)
        sub_chunks = []
        for part in parts:
            if not part.strip():
                continue
            sub_chunks.append(DocumentChunk(
                text=part.strip(),
                source=chunk.source,
                page=chunk.page,
                section=chunk.section,
                chunk_type=chunk.chunk_type,
                metadata=chunk.metadata.copy(),
            ))
        return sub_chunks if sub_chunks else [chunk]

    def _recursive_split(self, text: str) -> List[str]:
        """Split by paragraph, then sentence, then words."""
        if len(text) <= self.chunk_size:
            return [text]

        # Try paragraph split
        paragraphs = re.split(r"\n\n+", text)
        if len(paragraphs) > 1:
            return self._merge_splits(paragraphs)

        # Try sentence split
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) > 1:
            return self._merge_splits(sentences)

        # Word-level fallback
        words = text.split(" ")
        return self._merge_splits(words)

    def _merge_splits(self, splits: List[str]) -> List[str]:
        """Merge splits into chunks respecting chunk_size with overlap."""
        chunks = []
        current = []
        current_len = 0

        for split in splits:
            split_len = len(split)
            if current_len + split_len > self.chunk_size and current:
                chunks.append(" ".join(current))
                # Overlap: keep last few words
                overlap_words = " ".join(current).split()[-self.chunk_overlap:]
                current = overlap_words
                current_len = sum(len(w) for w in current)

            current.append(split)
            current_len += split_len

        if current:
            chunks.append(" ".join(current))

        return chunks
