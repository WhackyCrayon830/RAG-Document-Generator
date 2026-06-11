"""Multimodal ingestion support for images, OCR, and tables."""

from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class MediaType(str, Enum):
    """Types of media that can be extracted."""
    IMAGE = "image"
    TABLE = "table"
    TEXT = "text"
    DIAGRAM = "diagram"


@dataclass
class ExtractedMedia:
    """Extracted media from document."""
    media_id: str
    media_type: MediaType
    source_page: int
    content: str  # Text content or caption
    metadata: dict
    confidence: float  # 0-1, confidence of extraction
    raw_path: Optional[Path] = None  # Path to raw media file


class OCREngine:
    """Handle OCR for scanned documents."""

    def __init__(self, backend: str = "paddleocr", use_gpu: bool = False):
        """
        Initialize OCR engine.

        Args:
            backend: "paddleocr" or "tesseract"
            use_gpu: Whether to use GPU acceleration
        """
        self.backend = backend
        self.use_gpu = use_gpu
        self._engine = None

    def initialize(self):
        """Initialize OCR engine (lazy loading)."""
        if self._engine is not None:
            return

        if self.backend == "paddleocr":
            try:
                from paddleocr import PaddleOCR
                self._engine = PaddleOCR(
                    use_angle_cls=True,
                    use_gpu=self.use_gpu,
                    lang=["en"],
                )
                logger.info("Initialized PaddleOCR engine")
            except ImportError:
                logger.warning("PaddleOCR not installed, OCR disabled")
                self._engine = None
        elif self.backend == "tesseract":
            try:
                import pytesseract
                self._engine = pytesseract
                logger.info("Initialized Tesseract engine")
            except ImportError:
                logger.warning("Tesseract not installed, OCR disabled")
                self._engine = None

    def extract_text(self, image_path: Path) -> tuple[str, float]:
        """
        Extract text from image using OCR.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (extracted_text, confidence_score)
        """
        self.initialize()
        
        if self._engine is None:
            logger.warning(f"OCR engine not available, skipping {image_path}")
            return "", 0.0

        try:
            if self.backend == "paddleocr":
                result = self._engine.ocr(str(image_path), cls=True)
                
                # Extract text and calculate average confidence
                texts = []
                confidences = []
                
                if result:
                    for line in result:
                        if line:
                            for word_info in line:
                                text, conf = word_info[1], word_info[2]
                                texts.append(text)
                                confidences.append(conf)
                
                full_text = " ".join(texts)
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                return full_text, avg_confidence

            elif self.backend == "tesseract":
                text = self._engine.image_to_string(str(image_path))
                return text, 0.85  # Tesseract doesn't provide confidence

        except Exception as exc:
            logger.error(f"OCR extraction failed for {image_path}: {exc}")
            return "", 0.0

    def extract_layout(self, image_path: Path) -> dict:
        """
        Extract document layout information.

        Returns:
            Dict with layout analysis results
        """
        # Placeholder for layout extraction
        return {
            "has_columns": False,
            "has_headers": False,
            "has_tables": False,
            "text_regions": [],
        }


class TableExtractor:
    """Extract and structure table data."""

    def __init__(self):
        """Initialize table extractor."""
        self._detector = None

    def extract_tables(self, pdf_path: Path) -> list[ExtractedMedia]:
        """
        Extract tables from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of extracted tables
        """
        extracted = []

        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    
                    for table_num, table in enumerate(tables or []):
                        # Convert table to markdown format
                        markdown_table = self._table_to_markdown(table)
                        
                        media = ExtractedMedia(
                            media_id=f"table_{page_num}_{table_num}",
                            media_type=MediaType.TABLE,
                            source_page=page_num + 1,
                            content=markdown_table,
                            metadata={
                                "rows": len(table),
                                "cols": len(table[0]) if table else 0,
                            },
                            confidence=0.95,
                        )
                        extracted.append(media)

        except ImportError:
            logger.warning("pdfplumber not installed, table extraction unavailable")
        except Exception as exc:
            logger.error(f"Table extraction failed: {exc}")

        return extracted

    def _table_to_markdown(self, table: list[list[str]]) -> str:
        """Convert table to markdown format."""
        if not table:
            return ""

        lines = []
        
        # Header row
        if table:
            header = table[0]
            lines.append("| " + " | ".join(str(cell or "") for cell in header) + " |")
            lines.append("|" + "|".join(["-" * 5] * len(header)) + "|")

        # Data rows
        for row in table[1:]:
            lines.append("| " + " | ".join(str(cell or "") for cell in row) + " |")

        return "\n".join(lines)


class ImageExtractor:
    """Extract images and generate captions."""

    def __init__(self, caption_model: str = "blip"):
        """
        Initialize image extractor.

        Args:
            caption_model: Model for image captioning
        """
        self.caption_model = caption_model
        self._captioner = None

    def extract_images(self, pdf_path: Path) -> list[ExtractedMedia]:
        """
        Extract images from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of extracted images with captions
        """
        extracted = []

        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc):
                image_list = page.get_images()
                
                for img_index, img_ref in enumerate(image_list):
                    xref = img_ref[0]
                    
                    # Extract image
                    pix = fitz.Pixmap(doc, xref)
                    
                    # Save image
                    img_name = f"page_{page_num}_img_{img_index}.png"
                    img_path = Path("temp") / img_name
                    img_path.parent.mkdir(exist_ok=True)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        pix.save(str(img_path))
                    else:  # CMYK
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                        pix.save(str(img_path))
                    
                    # Generate caption
                    caption = self._generate_caption(img_path)
                    
                    media = ExtractedMedia(
                        media_id=f"image_{page_num}_{img_index}",
                        media_type=MediaType.IMAGE,
                        source_page=page_num + 1,
                        content=caption,
                        metadata={"filename": img_name},
                        confidence=0.9,
                        raw_path=img_path,
                    )
                    extracted.append(media)

        except ImportError:
            logger.warning("PyMuPDF not installed, image extraction unavailable")
        except Exception as exc:
            logger.error(f"Image extraction failed: {exc}")

        return extracted

    def _generate_caption(self, image_path: Path) -> str:
        """Generate caption for image."""
        try:
            from transformers import pipeline
            
            if self._captioner is None:
                self._captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
            
            caption = self._captioner(str(image_path))[0]["generated_text"]
            return caption

        except ImportError:
            return "Image extracted but captioning model not available"
        except Exception as exc:
            logger.warning(f"Image captioning failed: {exc}")
            return "Image extracted but captioning failed"


class MultimodalProcessor:
    """Process multimodal documents (images, tables, text)."""

    def __init__(self, enable_ocr: bool = True, enable_tables: bool = True, enable_images: bool = True):
        """Initialize multimodal processor."""
        self.ocr_engine = OCREngine() if enable_ocr else None
        self.table_extractor = TableExtractor() if enable_tables else None
        self.image_extractor = ImageExtractor() if enable_images else None

    def process_pdf(self, pdf_path: Path) -> dict:
        """
        Process PDF and extract all media.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with extracted media organized by type
        """
        result = {
            "source": str(pdf_path),
            "processed_at": str(Path(pdf_path).stat().st_mtime),
            "media": {
                "images": [],
                "tables": [],
                "text": [],
            },
        }

        # Extract tables
        if self.table_extractor:
            result["media"]["tables"] = self.table_extractor.extract_tables(pdf_path)

        # Extract images
        if self.image_extractor:
            result["media"]["images"] = self.image_extractor.extract_images(pdf_path)

        return result

    def process_scanned_document(self, pdf_path: Path) -> dict:
        """
        Process scanned document with OCR.

        Args:
            pdf_path: Path to scanned PDF

        Returns:
            Dict with OCR'd text and extracted media
        """
        if not self.ocr_engine:
            raise RuntimeError("OCR engine not initialized")

        result = {
            "source": str(pdf_path),
            "text_extracted_via_ocr": True,
            "pages": [],
        }

        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc):
                # Try text extraction first
                text = page.get_text()
                
                # If no text, use OCR
                if not text.strip():
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                    temp_image = Path("temp") / f"page_{page_num}.png"
                    temp_image.parent.mkdir(exist_ok=True)
                    pix.save(str(temp_image))
                    
                    text, confidence = self.ocr_engine.extract_text(temp_image)
                    temp_image.unlink(missing_ok=True)
                else:
                    confidence = 1.0

                result["pages"].append({
                    "page_number": page_num + 1,
                    "text": text,
                    "ocr_confidence": confidence,
                })

        except Exception as exc:
            logger.error(f"Scanned document processing failed: {exc}")

        return result
