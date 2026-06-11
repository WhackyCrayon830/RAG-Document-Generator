"""General helper utilities."""
import os
import json
from typing import List, Dict, Any


def load_json_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_prompt_file(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def list_files_in_dir(directory: str, extensions: List[str] = None) -> List[str]:
    if not os.path.exists(directory):
        return []
    files = []
    for f in os.listdir(directory):
        full = os.path.join(directory, f)
        if os.path.isfile(full):
            if extensions is None or os.path.splitext(f)[1].lower() in extensions:
                files.append(full)
    return files


def list_prompt_files(prompts_dir: str = "prompts") -> List[str]:
    return [
        os.path.basename(f)
        for f in list_files_in_dir(prompts_dir, [".txt"])
    ]


def list_local_models(models_dir: str = "models") -> List[str]:
    if not os.path.exists(models_dir):
        return []
    return [
        d for d in os.listdir(models_dir)
        if os.path.isdir(os.path.join(models_dir, d))
    ]


def format_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
