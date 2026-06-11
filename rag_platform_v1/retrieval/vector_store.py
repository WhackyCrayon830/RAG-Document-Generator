"""
FAISS vector store with disk persistence and incremental indexing.
Supports CPU and GPU (if available).
"""
import os
import json
import logging
import pickle
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

FAISS_INDEX_FILE = "vector_db/faiss.index"
METADATA_FILE = "vector_db/metadata.pkl"


class VectorStore:
    def __init__(self, embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.embedding_model_name = embedding_model_name
        self._embedder = None
        self._index = None
        self._metadata: List[Dict[str, Any]] = []  # parallel list to FAISS index
        self._dim: int = 384
        self._is_loaded = False

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            from services.hardware_detector import get_hardware_info
            hw = get_hardware_info()
            device = hw.device
            logger.info(f"Loading embedding model {self.embedding_model_name} on {device}")
            self._embedder = SentenceTransformer(self.embedding_model_name, device=device)
            self._dim = self._embedder.get_sentence_embedding_dimension()
        return self._embedder

    def _get_index(self):
        if self._index is None:
            import faiss
            self._index = faiss.IndexFlatL2(self._dim)
        return self._index

    def embed_texts(self, texts: List[str], batch_size: int = 16) -> "np.ndarray":
        import numpy as np
        embedder = self._get_embedder()
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            embs = embedder.encode(batch, show_progress_bar=False, normalize_embeddings=True)
            all_embeddings.append(embs)
        return np.vstack(all_embeddings).astype("float32")

    def add_chunks(self, chunks, progress_cb=None) -> int:
        """Add DocumentChunk objects to the vector store."""
        import numpy as np
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        meta = [c.to_dict() for c in chunks]

        if progress_cb:
            progress_cb(f"Embedding {len(texts)} chunks...")

        embeddings = self.embed_texts(texts)
        self._get_index().add(embeddings)
        self._metadata.extend(meta)

        logger.info(f"Added {len(chunks)} chunks. Total: {len(self._metadata)}")
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Search for similar chunks. Returns (metadata, score) tuples."""
        import numpy as np
        if self._index is None or len(self._metadata) == 0:
            return []

        query_emb = self.embed_texts([query])
        scores, indices = self._get_index().search(query_emb, min(top_k, len(self._metadata)))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            results.append((self._metadata[idx], float(score)))
        return results

    def save(self) -> bool:
        try:
            import faiss
            os.makedirs("vector_db", exist_ok=True)
            if self._index is not None:
                faiss.write_index(self._index, FAISS_INDEX_FILE)
            with open(METADATA_FILE, "wb") as f:
                pickle.dump(self._metadata, f)
            logger.info(f"Saved vector store: {len(self._metadata)} chunks")
            return True
        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
            return False

    def load(self) -> bool:
        try:
            import faiss
            if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(METADATA_FILE):
                self._index = faiss.read_index(FAISS_INDEX_FILE)
                with open(METADATA_FILE, "rb") as f:
                    self._metadata = pickle.load(f)
                self._is_loaded = True
                logger.info(f"Loaded vector store: {len(self._metadata)} chunks")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False

    def clear(self):
        import faiss
        self._index = faiss.IndexFlatL2(self._dim)
        self._metadata = []
        logger.info("Vector store cleared.")

    def rebuild(self, chunks, progress_cb=None):
        self.clear()
        return self.add_chunks(chunks, progress_cb)

    @property
    def chunk_count(self) -> int:
        return len(self._metadata)

    @property
    def is_ready(self) -> bool:
        return len(self._metadata) > 0


# Singleton
_vector_store: Optional[VectorStore] = None


def get_vector_store(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(embedding_model_name=model_name)
        _vector_store.load()
    return _vector_store
