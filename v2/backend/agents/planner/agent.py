import json
import re

from backend.agents.ollama_client import OllamaClient
from backend.config.settings import Settings


DEFAULT_SECTIONS = [
    "Executive Summary",
    "Background",
    "Requirements",
    "System Architecture",
    "Implementation Plan",
    "Validation and Risks",
    "Conclusion",
]


class PlannerAgent:
    def __init__(self, ollama: OllamaClient, settings: Settings, model: str | None = None):
        self.ollama = ollama
        self.settings = settings
        self.model = model or settings.ollama_planning_model

    def plan(self, prompt: str, required_sections: list[str] | None = None) -> list[dict]:
        if required_sections:
            titles = required_sections
        else:
            titles = self._ask_ollama(prompt) or DEFAULT_SECTIONS
        return [
            {
                "id": str(index + 1),
                "title": title.strip(),
                "dependencies": [] if index == 0 else [str(index)],
                "required_context": [title.strip(), prompt[:180]],
                "template_constraints": {},
            }
            for index, title in enumerate(titles)
            if title.strip()
        ]

    def _ask_ollama(self, prompt: str) -> list[str]:
        response = self.ollama.generate(
            self.model,
            f"Create a concise document section outline as JSON list of section titles only.\n\nRequest:\n{prompt}",
            "You are a document planning agent. Return only valid JSON.",
        )
        try:
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
        lines = [re.sub(r"^[0-9.\-\s]+", "", line).strip() for line in response.splitlines()]
        return [line for line in lines if line][:8]
