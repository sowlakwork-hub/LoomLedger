import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector
from app.config import Settings, get_settings


def connect_postgres(settings: Settings | None = None):
    """Create a connection to the PostgreSQL database."""

    if settings is None:
        settings = get_settings()

    con = psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        connect_timeout=5,
        row_factory=dict_row,
    )

    register_vector(con)
    return con


def test_postgres_connection() -> dict:
    """Test the PostgreSQL connection."""

    with connect_postgres() as con:
        row = con.execute(
            """
            SELECT
                current_database() AS database,
                current_user AS username,
                version() AS version
            """
        ).fetchone()

        return {
            "status": "connected",
            "database": row["database"],
            "username": row["username"],
            "version": row["version"],
        }