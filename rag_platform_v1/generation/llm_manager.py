"""
LLM Manager - loads and manages local (offline) or HuggingFace (online) models.
Supports Qwen, Mistral, Phi, DeepSeek and any HF-compatible model.
"""
import os
import logging
from typing import Optional, Generator

logger = logging.getLogger(__name__)


class LLMManager:
    def __init__(self):
        self._pipeline = None
        self._hf_client = None
        self._mode = "offline"  # "offline" or "online"
        self._model_id = ""
        self._is_loaded = False

    def load_offline(self, model_path: str) -> bool:
        """Load a local model from the models/ directory."""
        if not os.path.exists(model_path):
            logger.error(f"Model path not found: {model_path}")
            return False

        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
            import torch
            from services.hardware_detector import get_hardware_info

            hw = get_hardware_info()
            device = 0 if hw.has_cuda else -1  # -1 = CPU for transformers pipeline

            logger.info(f"Loading offline model from {model_path} on {hw.device}...")
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
            logger.error(f"Failed to load offline model: {e}")
            return False

    def load_online(self, model_id: str, hf_token: str) -> bool:
        """Use HuggingFace Inference API."""
        if not hf_token:
            logger.error("HuggingFace token required for online mode.")
            return False
        try:
            from huggingface_hub import InferenceClient
            self._hf_client = InferenceClient(model=model_id, token=hf_token)
            self._mode = "online"
            self._model_id = model_id
            self._is_loaded = True
            logger.info(f"Online HF model configured: {model_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to configure HF online model: {e}")
            return False

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.3,
        stream: bool = False,
    ) -> Generator[str, None, None]:
        """Generate text. Yields tokens if stream=True, else yields full response."""
        if not self._is_loaded:
            yield "[Model not loaded. Please load a model first.]"
            return

        if self._mode == "online":
            yield from self._generate_online(prompt, max_new_tokens, temperature, stream)
        else:
            yield from self._generate_offline(prompt, max_new_tokens, temperature, stream)

    def _generate_online(self, prompt, max_new_tokens, temperature, stream) -> Generator:
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

    def _generate_offline(self, prompt, max_new_tokens, temperature, stream) -> Generator:
        try:
            result = self._pipeline(
                prompt,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0,
                temperature=temperature if temperature > 0 else 1.0,
                return_full_text=False,
            )
            text = result[0]["generated_text"] if result else ""
            # Simulate streaming by yielding word chunks
            if stream:
                words = text.split(" ")
                for i in range(0, len(words), 5):
                    yield " ".join(words[i:i+5]) + " "
            else:
                yield text
        except Exception as e:
            yield f"[Generation error: {e}]"

    def unload(self):
        """Free model from memory."""
        self._pipeline = None
        self._hf_client = None
        self._is_loaded = False
        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model_id(self) -> str:
        return self._model_id


# Singleton
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
