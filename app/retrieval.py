
from pgvector import Vector

from app.config import get_settings
from app.embeddings import generate_embedding
from app.postgres import connect_postgres


def retrieve_document_chunks(
    question: str,
    limit: int = 5,
) -> list[dict]:
    """Retrieve the most relevant annual-report chunks."""

    if not question or not question.strip():
        return []

    if limit < 1:
        raise ValueError("limit must be at least 1")

    settings = get_settings()

    # Convert the question into a vector.
    question_embedding = generate_embedding(question)

    # Search PostgreSQL using cosine distance.
    with connect_postgres(settings) as con:
        rows = con.execute(
            """
            SELECT
                source_file,
                page_no,
                heading,
                chunk_text,
                embedding <=> %s AS distance
            FROM document_chunks
            WHERE embedding IS NOT NULL
            ORDER BY distance
            LIMIT %s
            """,
            (
                Vector(question_embedding),
                limit,
            ),
        ).fetchall()

    return [dict(row) for row in rows]
