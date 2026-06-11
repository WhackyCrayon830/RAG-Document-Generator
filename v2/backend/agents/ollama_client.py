import requests


class OllamaClient:
    def __init__(self, base_url: str, enabled: bool = True):
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled

    def generate(self, model: str, prompt: str, system: str | None = None) -> str:
        if not self.enabled:
            return ""
        payload = {"model": model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        try:
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=180)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.RequestException:
            return ""
