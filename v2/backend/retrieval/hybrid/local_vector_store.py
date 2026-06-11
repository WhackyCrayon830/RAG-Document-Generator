from dataclasses import dataclass
from pathlib import Path

import numpy as np
import re

from backend.storage.filesystem.json_store import read_json, write_json


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict


class LocalVectorStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = read_json(path, {"chunks": []})

    def save(self) -> None:
        write_json(self.path, self.data)

    def has_chunk(self, chunk_id: str) -> bool:
        return any(item["chunk_id"] == chunk_id for item in self.data["chunks"])

    def add_chunk(self, chunk_id: str, document_id: str, text: str, embedding: list[float], metadata: dict) -> None:
        if self.has_chunk(chunk_id):
            return
        self.data["chunks"].append(
            {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "text": text,
                "embedding": embedding,
                "metadata": metadata,
            }
        )

    def search(self, query_embedding: list[float], top_k: int = 8) -> list[SearchResult]:
        query = np.array(query_embedding, dtype=float)
        query_norm = np.linalg.norm(query) or 1.0
        results = []
        for item in self.data["chunks"]:
            vector = np.array(item["embedding"], dtype=float)
            score = float(np.dot(query, vector) / (query_norm * (np.linalg.norm(vector) or 1.0)))
            results.append(
                SearchResult(
                    chunk_id=item["chunk_id"],
                    document_id=item["document_id"],
                    text=item["text"],
                    score=score,
                    metadata=item.get("metadata", {}),
                )
            )
        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def hybrid_search(self, query: str, query_embedding: list[float], top_k: int = 8) -> list[SearchResult]:
        query_tokens = set(TOKEN_RE.findall(query.lower()))
        query_vector = np.array(query_embedding, dtype=float)
        query_norm = np.linalg.norm(query_vector) or 1.0
        results = []
        for item in self.data["chunks"]:
            vector = np.array(item["embedding"], dtype=float)
            vector_score = float(np.dot(query_vector, vector) / (query_norm * (np.linalg.norm(vector) or 1.0)))
            text_tokens = set(TOKEN_RE.findall(item["text"].lower()))
            keyword_score = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
            score = (0.72 * vector_score) + (0.28 * keyword_score)
            results.append(
                SearchResult(
                    chunk_id=item["chunk_id"],
                    document_id=item["document_id"],
                    text=item["text"],
                    score=score,
                    metadata={**item.get("metadata", {}), "vector_score": vector_score, "keyword_score": keyword_score},
                )
            )
        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]
