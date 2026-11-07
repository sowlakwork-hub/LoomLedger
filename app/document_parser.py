
import re
from pathlib import Path

from app.extract import (
    extract_pdf_text,
    ocr_page,
    clean_text,
    DEFAULT_DPI,
)

MIN_READABLE_TEXT = 80

CHUNK_SIZE = 3500
CHUNK_OVERLAP = 400


def is_heading(line: str) -> bool:
    line = line.strip()

    if len(line) < 4 or len(line) > 150:
        return False

    # Numbered headings, for example: 1. Company Overview
    if re.match(r"^\d+(?:\.\d+)*[.)]?\s+[A-Z]", line):
        return True

    known_headings = [
        "balance sheet",
        "statement of profit",
        "statement of cash flows",
        "cash flow statement",
        "notes to the financial statements",
        "notes to consolidated financial statements",
        "corporate governance",
        "auditors report",
        "directors report",
        "management discussion",
    ]

    if any(term in line.lower() for term in known_headings):
        return True

    letters = [char for char in line if char.isalpha()]

    if len(letters) >= 5:
        uppercase_ratio = (
            sum(char.isupper() for char in letters) / len(letters)
        )

        if uppercase_ratio >= 0.75:
            return True

    return False


def detect_heading(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()

        if line and is_heading(line):
            return line

    return None


def extract_document_pages(
    pdf_path: str | Path,
    dpi: int = DEFAULT_DPI,
) -> list[dict]:

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    # Reuse the existing PDF text extraction function.
    pages = extract_pdf_text(pdf_path)

    processed_pages = []
    current_heading = "General Content"

    for page in pages:
        page_no = page["page_no"]
        text = clean_text(page.get("text", ""))

        extraction_method = page.get(
            "extraction_method",
            "pdfplumber",
        )

        # Reuse the existing OCR function for scanned pages.
        if len(text) < MIN_READABLE_TEXT:
            text = ocr_page(
                pdf_path,
                page_no - 1,
                dpi=dpi,
            )

            text = clean_text(text)
            extraction_method = "tesseract_ocr"

        # Update the section heading when a new one is detected.
        detected_heading = detect_heading(text)

        if detected_heading:
            current_heading = detected_heading

        processed_pages.append({
            "source_file": pdf_path.name,
            "page_no": page_no,
            "heading": current_heading,
            "text": text,
            "extraction_method": extraction_method,
        })

        print(
            f"Processed page {page_no} "
            f"| Method: {extraction_method} "
            f"| Heading: {current_heading} "
            f"| Characters: {len(text)}"
        )

    return processed_pages


def chunk_pages(
    pages: list[dict],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict]:

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []

    for page in pages:
        text = page["text"].strip()

        if not text:
            continue

        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            # Try to end the chunk at a natural text boundary.
            if end < len(text):
                boundary = text.rfind("\n", start, end)

                if boundary < start + chunk_size // 2:
                    boundary = text.rfind(". ", start, end)

                if boundary >= start + chunk_size // 2:
                    end = boundary + 1

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    "source_file": page["source_file"],
                    "page_no": page["page_no"],
                    "heading": page["heading"],
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_text,
                    "extraction_method": page["extraction_method"],
                })

                chunk_index += 1

            if end >= len(text):
                break

            start = max(start + 1, end - overlap)

    return chunks
