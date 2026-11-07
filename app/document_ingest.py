
import sys
import time
from pathlib import Path

from google import genai
from pgvector import Vector

from app.config import get_settings
from app.document_parser import chunk_pages, extract_document_pages
from app.postgres import connect_postgres

BATCH_SIZE = 4
PAUSE_SECONDS = 10


def generate_embeddings(texts: list[str], client, settings) -> list[list[float]]:
    """Generate embeddings for a batch of document chunks."""

    response = client.models.embed_content(
        model=settings.embedding_model,
        contents=texts,
        config={
            "output_dimensionality": settings.embedding_dimensions,
        },
    )

    embeddings = [item.values for item in response.embeddings]

    if len(embeddings) != len(texts):
        raise RuntimeError("Embedding count does not match chunk count.")

    for embedding in embeddings:
        if len(embedding) != settings.embedding_dimensions:
            raise RuntimeError(
                f"Expected {settings.embedding_dimensions} dimensions, "
                f"received {len(embedding)}."
            )

    return embeddings



def store_chunks(chunks: list[dict], client, settings) -> int:
    """Generate embeddings and safely store chunks in PostgreSQL."""

    if not chunks:
        return 0

    stored = 0
    source_file = chunks[0]["source_file"]

    with connect_postgres(settings) as con:

        # Find chunks that already have embeddings.
        existing_rows = con.execute(
            """
            SELECT page_no, chunk_index
            FROM document_chunks
            WHERE source_file = %s
              AND embedding IS NOT NULL
            """,
            (source_file,),
        ).fetchall()

        existing = {
            (row["page_no"], row["chunk_index"])
            for row in existing_rows
        }

        # Skip chunks that were successfully stored earlier.
        pending_chunks = [
            chunk for chunk in chunks
            if (
                chunk["page_no"],
                chunk["chunk_index"],
            ) not in existing
        ]

        print(f"Already stored: {len(existing)}")
        print(f"Remaining chunks: {len(pending_chunks)}")

        for start in range(0, len(pending_chunks), BATCH_SIZE):
            batch = pending_chunks[start:start + BATCH_SIZE]

            texts = [chunk["chunk_text"] for chunk in batch]

            embeddings = generate_embeddings(
                texts,
                client,
                settings,
            )

            for chunk, embedding in zip(batch, embeddings, strict=True):
                con.execute(
                    """
                    INSERT INTO document_chunks (
                        source_file,
                        page_no,
                        heading,
                        chunk_index,
                        chunk_text,
                        embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (
                        source_file,
                        page_no,
                        chunk_index
                    )
                    DO UPDATE SET
                        heading = EXCLUDED.heading,
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        chunk["source_file"],
                        chunk["page_no"],
                        chunk["heading"],
                        chunk["chunk_index"],
                        chunk["chunk_text"],
                        Vector(embedding),
                    ),
                )

            # Commit each batch independently.
            # Earlier successful batches survive later failures.
            con.commit()

            stored += len(batch)

            print(
                f"Stored this run: {stored}/"
                f"{len(pending_chunks)} remaining chunks"
            )

            if start + BATCH_SIZE < len(pending_chunks):
                print(f"Waiting {PAUSE_SECONDS} seconds...")
                time.sleep(PAUSE_SECONDS)

    return stored



def ingest_pdf(pdf_path: Path, client, settings) -> dict:
    """Process one PDF from extraction to vector storage."""

    print(f"\nProcessing: {pdf_path.name}")

    pages = extract_document_pages(pdf_path)

    print(f"Pages extracted: {len(pages)}")

    chunks = chunk_pages(pages)

    print(f"Chunks generated: {len(chunks)}")

    if not chunks:
        print("No text chunks found. Skipping this PDF.")
        return {
            "file": pdf_path.name,
            "pages": len(pages),
            "chunks": 0,
            "stored": 0,
        }

    stored = store_chunks(chunks, client, settings)

    print(f"Completed: {pdf_path.name}")

    return {
        "file": pdf_path.name,
        "pages": len(pages),
        "chunks": len(chunks),
        "stored": stored,
    }


def main():
    if len(sys.argv) not in (2, 3):
        print(
            "Usage:\n"
            "  python -m app.document_ingest data/raw\n"
            "  python -m app.document_ingest data/raw kpr_mill_FY25.pdf"
        )
        sys.exit(1)

    raw_dir = Path(sys.argv[1])

    if not raw_dir.is_dir():
        raise NotADirectoryError(raw_dir)

    if len(sys.argv) == 3:
        pdf_path = raw_dir / sys.argv[2]

        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise FileNotFoundError(pdf_path)

        pdf_files = [pdf_path]
    else:
        pdf_files = sorted(raw_dir.glob("*.pdf"))

    if not pdf_files:
        print("No PDF files found.")
        return

    settings = get_settings()

    client = genai.Client(api_key=settings.gemini_api_key)

    results = []

    for pdf_path in pdf_files:
        result = ingest_pdf(pdf_path, client, settings)
        results.append(result)

    print("\n========== INGESTION SUMMARY ==========")

    total_pages = sum(item["pages"] for item in results)
    total_chunks = sum(item["chunks"] for item in results)
    total_stored = sum(item["stored"] for item in results)

    for item in results:
        print(
            f"{item['file']} | "
            f"Pages: {item['pages']} | "
            f"Chunks: {item['chunks']} | "
            f"Stored: {item['stored']}"
        )

    print("--------------------------------------")
    print("Total pages:", total_pages)
    print("Total chunks:", total_chunks)
    print("Total stored:", total_stored)
    print("Ingestion completed.")


if __name__ == "__main__":
    main()
