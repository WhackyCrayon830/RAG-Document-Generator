from backend.config.settings import get_settings
from backend.storage.qdrant.collections import ensure_qdrant_collections


if __name__ == "__main__":
    settings = get_settings()
    print(ensure_qdrant_collections(settings.qdrant_url))
