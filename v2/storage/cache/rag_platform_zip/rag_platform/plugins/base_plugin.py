"""Base plugin interface - all file processors must inherit from this."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class DocumentChunk:
    """A single chunk of text extracted from a document."""
    text: str
    source: str
    page: int = 0
    section: str = ""
    chunk_type: str = "text"  # text, table, code, heading
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "page": self.page,
            "section": self.section,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
        }


class BasePlugin(ABC):
    """
    Abstract base class for all document processors.
    Drop a new plugin into the plugins/ folder and register it
    in plugin_registry.py to support a new file type.
    """

    # Subclasses must declare which extensions they handle
    SUPPORTED_EXTENSIONS: List[str] = []

    @abstractmethod
    def extract(self, file_path: str) -> List[DocumentChunk]:
        """
        Extract content from the file and return a list of DocumentChunk objects.
        Each chunk should be a meaningful, self-contained piece of content.
        """
        ...

    def get_supported_extensions(self) -> List[str]:
        return [ext.lower() for ext in self.SUPPORTED_EXTENSIONS]

    def validate_file(self, file_path: str) -> bool:
        """Basic file existence check. Override for stricter validation."""
        import os
        return os.path.exists(file_path) and os.path.getsize(file_path) > 0
