"""Structured logging setup."""
import logging
import sys
from typing import List


class ListHandler(logging.Handler):
    """Captures log records into a list for display in the UI."""
    def __init__(self, log_list: List[str], level=logging.DEBUG):
        super().__init__(level)
        self.log_list = log_list

    def emit(self, record):
        msg = self.format(record)
        self.log_list.append(msg)
        if len(self.log_list) > 500:
            self.log_list.pop(0)


def setup_logging(ui_log_list: List[str] = None) -> logging.Logger:
    """Configure logging for the application."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers = [logging.StreamHandler(sys.stdout)]
    if ui_log_list is not None:
        list_handler = ListHandler(ui_log_list)
        list_handler.setFormatter(logging.Formatter(fmt, datefmt))
        handlers.append(list_handler)

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )
    return logging.getLogger("rag_platform")
