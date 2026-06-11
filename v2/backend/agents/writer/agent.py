from backend.agents.ollama_client import OllamaClient
from backend.config.settings import Settings
from backend.retrieval.hybrid.local_vector_store import SearchResult


class WriterAgent:
    def __init__(self, ollama: OllamaClient, settings: Settings, model: str | None = None):
        self.ollama = ollama
        self.settings = settings
        self.model = model or settings.ollama_writing_model

    def write_section(self, title: str, goal: str, context: list[SearchResult], adjacent_summary: str = "") -> str:
        context_block = "\n\n".join(
            f"[{idx + 1}] {item.text}\nSource: {item.metadata.get('filename', item.document_id)}"
            for idx, item in enumerate(context)
        )
        prompt = f"""
Write one document section.

Section title: {title}
Section goal: {goal}
Adjacent summary: {adjacent_summary}

Use only this scoped context. Add bracket citations like [1] when making factual claims.

Context:
{context_block or "No retrieved context available. Keep the section general and mark assumptions clearly."}
"""
        response = self.ollama.generate(
            self.model,
            prompt,
            "You are a careful technical writer. Do not invent source-backed facts.",
        )
        if response:
            return response
        return self._fallback(title, context)

    def _fallback(self, title: str, context: list[SearchResult]) -> str:
        if not context:
            return f"{title}\n\nNo local evidence was found for this section. Add source documents and regenerate for richer content."
        bullets = "\n".join(f"- {item.text[:420].strip()} [{idx + 1}]" for idx, item in enumerate(context[:4]))
        return f"{title}\n\nKey source-backed points:\n{bullets}"
