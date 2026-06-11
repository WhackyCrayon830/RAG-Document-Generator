"""
Folder watcher - monitors a directory for new files and triggers ingestion.
Uses watchdog for cross-platform file system events.
"""
import os
import logging
import threading
from typing import Callable, List

logger = logging.getLogger(__name__)


class FolderWatcher:
    """Watches a folder and calls a callback when new files are added."""

    def __init__(self, folder: str, callback: Callable[[str], None], extensions: List[str] = None):
        self.folder = folder
        self.callback = callback
        self.extensions = [e.lower() for e in (extensions or [])]
        self._observer = None
        self._running = False

    def start(self):
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            watcher = self

            class Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if event.is_directory:
                        return
                    ext = os.path.splitext(event.src_path)[1].lower()
                    if not watcher.extensions or ext in watcher.extensions:
                        logger.info(f"New file detected: {event.src_path}")
                        try:
                            watcher.callback(event.src_path)
                        except Exception as e:
                            logger.error(f"Callback failed for {event.src_path}: {e}")

            self._observer = Observer()
            self._observer.schedule(Handler(), self.folder, recursive=False)
            self._observer.start()
            self._running = True
            logger.info(f"Watching folder: {self.folder}")
        except ImportError:
            logger.warning("watchdog not installed. Folder watching disabled.")
        except Exception as e:
            logger.error(f"Failed to start folder watcher: {e}")

    def stop(self):
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join()
            self._running = False
            logger.info("Folder watcher stopped.")

    @property
    def is_running(self) -> bool:
        return self._running
