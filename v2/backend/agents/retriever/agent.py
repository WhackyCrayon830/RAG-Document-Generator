from backend.ingestion.embeddings.local_embeddings import EmbeddingClient
from backend.retrieval.hybrid.local_vector_store import LocalVectorStore, SearchResult


class RetrieverAgent:
    def __init__(self, embeddings: EmbeddingClient, vector_store: LocalVectorStore):
        self.embeddings = embeddings
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 8) -> list[SearchResult]:
        return self.vector_store.hybrid_search(query, self.embeddings.embed(query), top_k=top_k)
