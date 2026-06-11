"""Hardware detector - auto-detects CPU/GPU at startup."""
import logging
import os

logger = logging.getLogger(__name__)


class HardwareInfo:
    def __init__(self):
        self.has_cuda: bool = False
        self.gpu_name: str = ""
        self.gpu_memory_gb: float = 0.0
        self.cpu_cores: int = os.cpu_count() or 1
        self.device: str = "cpu"
        self.torch_dtype: str = "float32"
        self.embedding_batch_size: int = 16
        self.generation_batch_size: int = 1


def detect_hardware() -> HardwareInfo:
    info = HardwareInfo()
    try:
        import torch
        if torch.cuda.is_available():
            info.has_cuda = True
            info.device = "cuda"
            info.gpu_name = torch.cuda.get_device_name(0)
            info.gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            info.torch_dtype = "float16"
            info.embedding_batch_size = 64
            logger.info(f"GPU detected: {info.gpu_name} ({info.gpu_memory_gb:.1f} GB)")
        else:
            logger.info("No CUDA GPU detected. Running in CPU mode.")
    except ImportError:
        logger.warning("PyTorch not available. Defaulting to CPU mode.")

    return info


# Singleton
_hw_info: HardwareInfo = None


def get_hardware_info() -> HardwareInfo:
    global _hw_info
    if _hw_info is None:
        _hw_info = detect_hardware()
    return _hw_info
