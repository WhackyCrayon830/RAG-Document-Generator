import requests


COLLECTIONS = {
    "document_chunks": 768,
    "image_chunks": 768,
    "table_chunks": 768,
    "summaries": 768,
    "templates": 768,
}


def ensure_qdrant_collections(qdrant_url: str) -> dict:
    base = qdrant_url.rstrip("/")
    results = {}
    for name, size in COLLECTIONS.items():
        response = requests.put(
            f"{base}/collections/{name}",
            json={"vectors": {"size": size, "distance": "Cosine"}},
            timeout=20,
        )
        results[name] = {"status_code": response.status_code, "ok": response.ok}
    return results
