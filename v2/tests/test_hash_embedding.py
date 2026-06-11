from backend.ingestion.embeddings.local_embeddings import EmbeddingClient


def test_hash_embedding_is_deterministic_when_ollama_disabled():
    client = EmbeddingClient("http://localhost:11434", "nomic-embed-text", use_ollama=False)
    first = client.embed("offline rag")
    second = client.embed("offline rag")
    assert first == second
    assert len(first) == 384
