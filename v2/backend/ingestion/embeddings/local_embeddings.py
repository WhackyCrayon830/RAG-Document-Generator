import hashlib
import math
import re

import numpy as np
import requests


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


class EmbeddingClient:
    def __init__(self, base_url: str, model: str, use_ollama: bool = True, dimensions: int = 384):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.use_ollama = use_ollama
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        if self.use_ollama:
            try:
                response = requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=60,
                )
                response.raise_for_status()
                vector = response.json().get("embedding")
                if vector:
                    return vector
            except requests.RequestException:
                pass
        return self._hash_embedding(text)

    def _hash_embedding(self, text: str) -> list[float]:
        vector = np.zeros(self.dimensions, dtype=float)
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1 if digest[4] % 2 == 0 else -1
            vector[index] += sign
        norm = math.sqrt(float(np.dot(vector, vector))) or 1.0
        return (vector / norm).tolist()
