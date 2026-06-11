from pathlib import Path


PROJECT_DIRS = ["raw", "parsed", "templates", "generated", "cache", "logs", "runs", "exports"]


def ensure_project_layout(root: Path) -> dict[str, Path]:
    paths = {}
    for name in PROJECT_DIRS:
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        paths[name] = path
    return paths
