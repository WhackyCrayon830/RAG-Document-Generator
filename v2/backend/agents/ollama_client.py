from __future__ import annotations

import httpx


class OllamaClient:
    def __init__(self, base_url: str, enabled: bool = True):
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled
        self.client = httpx.Client(timeout=300)

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        images: list[str] | None = None,
    ) -> str:
        """Generate a completion.

        Args:
            model:   Ollama model name.
            prompt:  User prompt text.
            system:  Optional system prompt.
            images:  Optional list of base64-encoded PNG/JPG strings (for VLM models).
        """
        if not self.enabled:
            return ""

        payload: dict = {"model": model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        if images:
            payload["images"] = images

        try:
            response = self.client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except httpx.RequestError as exc:
            return ""
        except Exception:
            return ""

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass
