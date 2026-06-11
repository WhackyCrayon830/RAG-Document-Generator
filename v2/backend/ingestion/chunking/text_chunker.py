from dataclasses import dataclass


@dataclass
class Chunk:
    index: int
    text: str


def chunk_text(text: str, max_chars: int = 1600, overlap: int = 220) -> list[Chunk]:
    normalized = "\n".join(line.strip() for line in text.splitlines())
    normalized = "\n".join(part for part in normalized.splitlines() if part)
    if not normalized:
        return []

    chunks: list[Chunk] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            split_at = normalized.rfind("\n", start, end)
            if split_at > start + 400:
                end = split_at
        text_slice = normalized[start:end].strip()
        if text_slice:
            chunks.append(Chunk(index=len(chunks), text=text_slice))
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks
