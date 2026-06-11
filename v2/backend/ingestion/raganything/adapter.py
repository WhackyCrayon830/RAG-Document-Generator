from pathlib import Path

from backend.ingestion.parsers.document_parser import parse_document


class RagAnythingAdapter:
    """Offline placeholder for RAG-Anything integration.

    The MVP keeps the boundary explicit so MinerU, Docling, PaddleOCR, and
    RAG-Anything can replace this parser without changing the ingestion API.
    """

    def parse(self, path: Path) -> str:
        return parse_document(path)
