from app.embeddings import generate_embedding
from app.postgres import connect_postgres
from pgvector import Vector


def main():
    sample = (
        "KPR Mill reported revenue from operations "
        "in its annual financial statement."
    )

    print("1. Generating Gemini embedding...")
    vector = generate_embedding(sample)

    print("Dimensions:", len(vector))

    print("2. Connecting to PostgreSQL...")

    with connect_postgres() as con:

        con.execute(
            """
            INSERT INTO document_chunks
            (
                source_file,
                page_no,
                heading,
                chunk_index,
                chunk_text,
                embedding
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_file, page_no, chunk_index)
            DO UPDATE SET
                chunk_text = EXCLUDED.chunk_text,
                embedding = EXCLUDED.embedding
            """,
            (
                "embedding_test",
                0,
                "Test heading",
                0,
                sample,
                vector,
            ),
        )

        print("3. Vector stored successfully!")

        result = con.execute(
            """
            SELECT
                source_file,
                page_no,
                embedding <=> %s AS distance
            FROM document_chunks
            ORDER BY embedding <=> %s
            LIMIT 1
            """,
            (Vector(vector), Vector(vector)),
        ).fetchone()

        print("4. Similarity search result:")
        print(result)

        assert result["source_file"] == "embedding_test"
        assert abs(float(result["distance"])) < 0.000001

        print("\nSUCCESS: Vector storage and retrieval verified!")


if __name__ == "__main__":
    main()