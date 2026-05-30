from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None


@dataclass
class OCRResult:
    text: str
    method: str
    page_count: int
    warnings: List[str] = field(default_factory=list)


class PDFTextReader:
    """Extract text from PDFs, with OCR fallback using pytesseract."""

    def extract_text(self, pdf_path: str | Path) -> OCRResult:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if PdfReader is None:
            raise RuntimeError("Install 'pypdf' to extract PDF text")

        text_chunks: List[str] = []
        warnings: List[str] = []
        reader = PdfReader(str(pdf_path))

        for page_index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_chunks.append(f"[PAGE {page_index}]\n{page_text.strip()}")
                continue

            warnings.append(f"Page {page_index} had no native text extraction")
            ocr_text = self._ocr_page(pdf_path, page_index)
            text_chunks.append(f"[PAGE {page_index} OCR]\n{ocr_text.strip()}")

        if not text_chunks:
            raise RuntimeError("No text could be extracted from PDF")

        return OCRResult(
            text="\n\n".join(text_chunks),
            method="native+ocr" if warnings else "native",
            page_count=len(reader.pages),
            warnings=warnings,
        )

    def _ocr_page(self, pdf_path: Path, page_index: int) -> str:
        if pytesseract is None:
            raise RuntimeError("Install 'pytesseract' and tesseract-ocr for OCR fallback")
        if Image is None:
            raise RuntimeError("Install 'Pillow' for OCR image conversion")
        if convert_from_path is None:
            raise RuntimeError("Install 'pdf2image' for PDF page rendering")

        images = convert_from_path(str(pdf_path), first_page=page_index, last_page=page_index)
        if not images:
            return ""

        image = images[0]
        text = pytesseract.image_to_string(image)
        return text

    def split_lines(self, text: str) -> List[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
