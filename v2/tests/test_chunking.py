from backend.ingestion.chunking.text_chunker import chunk_text


def test_chunk_text_returns_overlapping_chunks():
    text = " ".join(["alpha beta gamma"] * 400)
    chunks = chunk_text(text, max_chars=500, overlap=50)
    assert len(chunks) > 1
    assert chunks[0].index == 0
    assert all(chunk.text for chunk in chunks)
