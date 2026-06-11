"""
LLM Manager - loads and manages local (offline), HuggingFace (online),
or Ollama models.

Supports:
- Local Transformers models
- HuggingFace Inference API
- Ollama models (Gemma, Qwen, Llama, Mistral, DeepSeek, etc.)
"""

import os
import logging
from typing import Optional, Generator

logger = logging.getLogger(__name__)


class LLMManager:
    def __init__(self):
        self._pipeline = None
        self._hf_client = None
        self._ollama_client = None

        self._mode = "offline"  # offline | online | ollama
        self._model_id = ""
        self._is_loaded = False

    # ------------------------------------------------------------------
    # Offline Transformers
    # ------------------------------------------------------------------

    def load_offline(self, model_path: str) -> bool:
        if not os.path.exists(model_path):
            logger.error(f"Model path not found: {model_path}")
            return False

        try:
            from transformers import pipeline
            import torch
            from services.hardware_detector import get_hardware_info

            hw = get_hardware_info()
            device = 0 if hw.has_cuda else -1

            logger.info(f"Loading offline model from {model_path} on {hw.device}")

            self._pipeline = pipeline(
                "text-generation",
                model=model_path,
                device=device,
                torch_dtype=torch.float16 if hw.has_cuda else torch.float32,
                trust_remote_code=True,
            )

            self._mode = "offline"
            self._model_id = model_path
            self._is_loaded = True

            logger.info("Offline model loaded successfully.")
            return True

        except Exception as e:
            logger.exception(e)
            return False

    # ------------------------------------------------------------------
    # HuggingFace API
    # ------------------------------------------------------------------

    def load_online(
        self,
        model_id: str,
        hf_token: str,
    ) -> bool:

        if not hf_token:
            logger.error("HF token required.")
            return False

        try:
            from huggingface_hub import InferenceClient

            self._hf_client = InferenceClient(
                model=model_id,
                token=hf_token,
            )

            self._mode = "online"
            self._model_id = model_id
            self._is_loaded = True

            logger.info(f"HuggingFace model configured: {model_id}")

            return True

        except Exception as e:
            logger.exception(e)
            return False

    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------

    def load_ollama(
        self,
        model_name: str,
        host: str = "http://localhost:11434",
    ) -> bool:

        try:
            import ollama

            self._ollama_client = ollama.Client(host=host)

            # Verify server connection
            self._ollama_client.list()

            self._mode = "ollama"
            self._model_id = model_name
            self._is_loaded = True

            logger.info(f"Ollama model configured: {model_name}")

            return True

        except Exception as e:
            logger.exception(f"Failed loading Ollama: {e}")
            return False

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.3,
        stream: bool = False,
    ) -> Generator[str, None, None]:

        if not self._is_loaded:
            yield "[Model not loaded. Please load a model first.]"
            return

        if self._mode == "online":
            yield from self._generate_online(
                prompt,
                max_new_tokens,
                temperature,
                stream,
            )

        elif self._mode == "ollama":
            yield from self._generate_ollama(
                prompt,
                max_new_tokens,
                temperature,
                stream,
            )

        else:
            yield from self._generate_offline(
                prompt,
                max_new_tokens,
                temperature,
                stream,
            )

    # ------------------------------------------------------------------
    # HF Generation
    # ------------------------------------------------------------------

    def _generate_online(
        self,
        prompt,
        max_new_tokens,
        temperature,
        stream,
    ):

        try:

            if stream:

                for token in self._hf_client.text_generation(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    stream=True,
                ):
                    yield token

            else:

                result = self._hf_client.text_generation(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                )

                yield result

        except Exception as e:
            yield f"[HuggingFace API error: {e}]"

    # ------------------------------------------------------------------
    # Ollama Generation
    # ------------------------------------------------------------------

    def _generate_ollama(
        self,
        prompt,
        max_new_tokens,
        temperature,
        stream,
    ):

        try:
            response = self._ollama_client.chat(
                model=self._model_id,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                stream=stream,
                options={
                    "num_predict": max_new_tokens,
                    "temperature": temperature,
                },
            )

            # ---------------------------
            # STREAMING MODE
            # ---------------------------
            if stream:

                for chunk in response:

                    # CASE 1: object-style (new ollama lib)
                    if hasattr(chunk, "message") and chunk.message:
                        content = getattr(chunk.message, "content", "")
                        if content:
                            yield content
                        continue

                    # CASE 2: dict-style (older fallback)
                    if isinstance(chunk, dict):
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content

            # ---------------------------
            # NON-STREAM MODE
            # ---------------------------
            else:

                if hasattr(response, "message"):
                    yield response.message.content
                elif isinstance(response, dict):
                    yield response.get("message", {}).get("content", "")
                else:
                    yield str(response)

        except Exception as e:
            yield f"[Ollama error: {e}]"

    # ------------------------------------------------------------------
    # Offline Generation
    # ------------------------------------------------------------------

    def _generate_offline(
        self,
        prompt,
        max_new_tokens,
        temperature,
        stream,
    ):

        try:

            result = self._pipeline(
                prompt,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0,
                temperature=temperature if temperature > 0 else 1.0,
                return_full_text=False,
            )

            text = result[0]["generated_text"] if result else ""

            if stream:

                words = text.split()

                for i in range(
                    0,
                    len(words),
                    5,
                ):
                    yield (" ".join(words[i : i + 5]) + " ")

            else:
                yield text

        except Exception as e:
            yield f"[Generation error: {e}]"

    # ------------------------------------------------------------------
    # Ollama Model Discovery
    # ------------------------------------------------------------------

    @staticmethod
    def get_ollama_models(
        host="http://localhost:11434",
    ):
        try:
            import ollama

            client = ollama.Client(host=host)

            models = client.list()

            if isinstance(models, dict):

                return [
                    m.get("model", "")
                    for m in models.get(
                        "models",
                        [],
                    )
                ]

            return []

        except Exception:
            return []

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def unload(self):

        self._pipeline = None
        self._hf_client = None
        self._ollama_client = None

        self._is_loaded = False

        try:
            import gc
            import torch

            gc.collect()

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except Exception:
            pass

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_loaded(self):
        return self._is_loaded

    @property
    def mode(self):
        return self._mode

    @property
    def model_id(self):
        return self._model_id


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------

_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    global _llm_manager

    if _llm_manager is None:
        _llm_manager = LLMManager()

    return _llm_manager
