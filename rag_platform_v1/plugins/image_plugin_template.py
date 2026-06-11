"""
IMAGE OCR PLUGIN TEMPLATE
=========================
This is a template showing how to add image/OCR support.

To activate:
  1. Install: pip install pytesseract Pillow
  2. Install Tesseract: https://github.com/tesseract-ocr/tesseract
  3. Rename this file: image_plugin.py
  4. Remove the `_DISABLED` suffix from the class name

The plugin is NOT loaded until the class is named correctly (no underscore prefix).
"""
import os
from typing import List
from plugins.base_plugin import BasePlugin, DocumentChunk


class ImagePlugin_DISABLED(BasePlugin):
    """OCR plugin for image files - activate by removing _DISABLED suffix."""
    SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]

    def extract(self, file_path: str) -> List[DocumentChunk]:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise ImportError(
                "Install: pip install pytesseract Pillow\n"
                "And install Tesseract OCR: https://github.com/tesseract-ocr/tesseract"
            )

        if not self.validate_file(file_path):
            return []

        source = os.path.basename(file_path)
        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img).strip()
            if text:
                return [DocumentChunk(
                    text=text,
                    source=source,
                    page=1,
                    section="",
                    chunk_type="text",
                    metadata={"ocr": True},
                )]
        except Exception as e:
            return [DocumentChunk(
                text=f"[OCR ERROR: {e}]",
                source=source,
                page=0,
                chunk_type="error",
            )]
        return []
