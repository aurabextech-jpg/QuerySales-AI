"""Document text extraction (plan §9, §10).

Supported formats: .txt, .md, .pdf.
Validates extension allowlist, max size 10 MB, non-empty after extraction.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class ExtractionError(Exception):
    """Raised when a file cannot be extracted (bad format, too large, empty)."""


def validate_file(filename: str, content_length: int) -> None:
    """Validate extension and size before attempting extraction."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ExtractionError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if content_length > MAX_FILE_SIZE:
        raise ExtractionError(
            f"File is {content_length / (1024*1024):.1f} MB, maximum is 10 MB."
        )
    if content_length == 0:
        raise ExtractionError("File is empty.")


def extract_text(filename: str, raw_bytes: bytes) -> str:
    """Extract plain text from uploaded file bytes.

    Returns the extracted text, or raises ExtractionError on failure.
    """
    validate_file(filename, len(raw_bytes))
    ext = Path(filename).suffix.lower()

    if ext in (".txt", ".md"):
        text = raw_bytes.decode("utf-8", errors="replace")

    elif ext == ".pdf":
        try:
            from pypdf import PdfReader
            import io

            reader = PdfReader(io.BytesIO(raw_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(pages)
        except Exception as exc:
            logger.error("PDF extraction failed for %s: %s", filename, exc, exc_info=True)
            raise ExtractionError("Could not read this PDF file.") from exc

    else:
        raise ExtractionError(f"Unsupported file type: {ext}")

    # Strip and check non-empty
    text = text.strip()
    if not text:
        raise ExtractionError(
            "File contained no readable text after extraction."
        )
    return text
