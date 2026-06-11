from backend.agents.ollama_client import OllamaClient
from backend.config.settings import Settings


class ValidatorAgent:
    def __init__(self, ollama: OllamaClient, settings: Settings, model: str | None = None):
        self.ollama = ollama
        self.settings = settings
        self.model = model or settings.ollama_validation_model

    def validate(self, section_title: str, content: str) -> dict:
        issues = []
        if "[" not in content:
            issues.append("No citations found in section content.")
        if len(content.split()) < 80:
            issues.append("Section may be too short for a production document.")
        verdict = "pass" if not issues else "review"
        return {"section": section_title, "verdict": verdict, "issues": issues}
