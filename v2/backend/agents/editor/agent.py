from backend.agents.ollama_client import OllamaClient
from backend.config.settings import Settings


class EditorAgent:
    def __init__(self, ollama: OllamaClient, settings: Settings, model: str | None = None):
        self.ollama = ollama
        self.settings = settings
        self.model = model or settings.ollama_editing_model

    def edit(self, title: str, content: str) -> str:
        response = self.ollama.generate(
            self.model,
            f"Polish this document section for clarity while preserving citations and facts.\n\nTitle: {title}\n\n{content}",
            "You are an editor. Preserve citations and do not add unsupported facts.",
        )
        return response or content
