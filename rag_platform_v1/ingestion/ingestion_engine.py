"""
Ingestion engine - orchestrates file processing end-to-end.
Handles plugin dispatch, chunking, and vector store updates.
"""
import os
import logging
from typing import List, Callable, Optional

from ingestion.plugin_registry import registry
from ingestion.chunker import Chunker
from plugins.base_plugin import DocumentChunk

logger = logging.getLogger(__name__)


class IngestionEngine:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunker = Chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._ensure_plugins_loaded()

    def _ensure_plugins_loaded(self):
        if not registry.supported_extensions():
            registry.discover_and_load()

    def ingest_file(
        self,
        file_path: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> List[DocumentChunk]:
        """Process a single file and return chunked DocumentChunks."""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return []

        plugin = registry.get_plugin(file_path)
        if plugin is None:
            ext = os.path.splitext(file_path)[1]
            logger.warning(f"No plugin for extension: {ext}")
            return []

        if progress_cb:
            progress_cb(f"Extracting {os.path.basename(file_path)}...")

        try:
            raw_chunks = plugin.extract(file_path)
            logger.info(f"Extracted {len(raw_chunks)} raw chunks from {file_path}")
        except Exception as e:
            logger.error(f"Plugin failed for {file_path}: {e}")
            return []

        if progress_cb:
            progress_cb(f"Chunking {os.path.basename(file_path)}...")

        chunks = self.chunker.chunk(raw_chunks)
        logger.info(f"Final chunk count for {file_path}: {len(chunks)}")
        return chunks

    def ingest_folder(
        self,
        folder_path: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> List[DocumentChunk]:
        """Ingest all supported files in a folder."""
        all_chunks: List[DocumentChunk] = []
        supported = registry.supported_extensions()

        files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if os.path.splitext(f)[1].lower() in supported
        ]

        for file_path in files:
            chunks = self.ingest_file(file_path, progress_cb)
            all_chunks.extend(chunks)

        return all_chunks

    def ingest_files(
        self,
        file_paths: List[str],
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> List[DocumentChunk]:
        """Ingest a list of file paths."""
        all_chunks: List[DocumentChunk] = []
        for file_path in file_paths:
            chunks = self.ingest_file(file_path, progress_cb)
            all_chunks.extend(chunks)
        return all_chunks
