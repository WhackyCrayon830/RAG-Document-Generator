"""Retriever - wraps vector store with confidence scoring and source formatting."""
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Lower L2 distance = more similar. Threshold for "confident" retrieval.
CONFIDENCE_THRESHOLD = 1.2


class RetrievedChunk:
    def __init__(self, text: str, source: str, page: int, section: str,
                 chunk_type: str, score: float, metadata: Dict[str, Any]):
        self.text = text
        self.source = source
        self.page = page
        self.section = section
        self.chunk_type = chunk_type
        self.score = score
        self.confidence = self._compute_confidence(score)
        self.metadata = metadata

    def _compute_confidence(self, score: float) -> str:
        if score < 0.5:
            return "high"
        elif score < CONFIDENCE_THRESHOLD:
            return "medium"
        else:
            return "low"

    def to_context_string(self) -> str:
        loc = f"[{self.source}"
        if self.page:
            loc += f", p.{self.page}"
        if self.section:
            loc += f", §{self.section}"
        loc += f"] [{self.confidence} confidence]"
        return f"{loc}\n{self.text}"


class Retriever:
    def __init__(self, vector_store, top_k: int = 5):
        self.vs = vector_store
        self.top_k = top_k

    def retrieve(self, query: str, top_k: int = None) -> List[RetrievedChunk]:
        k = top_k or self.top_k
        raw = self.vs.search(query, top_k=k)
        results = []
        for meta, score in raw:
            results.append(RetrievedChunk(
                text=meta.get("text", ""),
                source=meta.get("source", "unknown"),
                page=meta.get("page", 0),
                section=meta.get("section", ""),
                chunk_type=meta.get("chunk_type", "text"),
                score=score,
                metadata=meta.get("metadata", {}),
            ))
        return results

    def build_context(self, chunks: List[RetrievedChunk]) -> str:
        if not chunks:
            return ""
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"--- Source {i} ---\n{chunk.to_context_string()}")
        return "\n\n".join(parts)

    def has_relevant_results(self, chunks: List[RetrievedChunk]) -> bool:
        """Returns True if at least one chunk has medium or high confidence."""
        return any(c.confidence in ("high", "medium") for c in chunks)
