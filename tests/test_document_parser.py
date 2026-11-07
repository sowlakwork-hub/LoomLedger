
from pathlib import Path

from app.document_parser import chunk_pages, extract_document_pages

PDF_PATH = Path("data/raw/kpr_mill_FY25.pdf")


def main():
    print("Starting document parser test...")

    pages = extract_document_pages(PDF_PATH)
    chunks = chunk_pages(pages)

    print("\n========== TEST RESULTS ==========")
    print("Total pages:", len(pages))
    print("Total chunks:", len(chunks))

    if pages:
        print("\nFirst page:")
        print("Page number:", pages[0]["page_no"])
        print("Heading:", pages[0]["heading"])
        print("Extraction method:", pages[0]["extraction_method"])
        print("Text preview:", pages[0]["text"][:300])

    if chunks:
        print("\nFirst chunk:")
        print("Page number:", chunks[0]["page_no"])
        print("Heading:", chunks[0]["heading"])
        print("Chunk index:", chunks[0]["chunk_index"])
        print("Chunk length:", len(chunks[0]["chunk_text"]))

    print("\nParser test completed.")


if __name__ == "__main__":
    main()
