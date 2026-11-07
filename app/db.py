import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY,
  company TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  basis TEXT NOT NULL CHECK (basis IN ('standalone','consolidated')),
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL DEFAULT 'INR_crore',
  source_file TEXT NOT NULL,
  page_no INTEGER NOT NULL,
  extraction_method TEXT NOT NULL DEFAULT 'manual',
  needs_review INTEGER NOT NULL DEFAULT 0,
  UNIQUE (company, fiscal_year, basis, metric)
);
CREATE TABLE IF NOT EXISTS pages (
  source_file TEXT NOT NULL,
  page_no INTEGER NOT NULL,
  text TEXT NOT NULL,
  PRIMARY KEY (source_file, page_no)
);
CREATE TABLE IF NOT EXISTS metric_disclosure_status (
  company TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  basis TEXT NOT NULL CHECK (basis IN ('standalone','consolidated')),
  metric TEXT NOT NULL,
  disclosure_status TEXT NOT NULL CHECK (
    disclosure_status IN (
        'REPORTED_VALUE',
        'NOT_SEPARATELY_REPORTED',
        'EXTRACTION_NOT_FOUND'
    )
),
  source_file TEXT NOT NULL,
  page_no INTEGER NOT NULL,
  note TEXT NOT NULL,
  PRIMARY KEY (company, fiscal_year, basis, metric)
);
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    input_cost REAL NOT NULL DEFAULT 0,
    output_cost REAL NOT NULL DEFAULT 0,
    total_cost REAL NOT NULL DEFAULT 0,
    question TEXT
);
"""


def connect(path: str, read_only: bool = False) -> sqlite3.Connection:
    p = Path(path)
    if read_only:
        con = sqlite3.connect(f"file:{p.resolve().as_posix()}?mode=ro", uri=True)
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    return con


def record_llm_usage(
    db_path: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    estimated_cost_usd: float | None,
) -> None:
    """Save one successful LLM response's usage."""

    con = connect(db_path)

    try:
        with con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    model TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    estimated_cost_usd REAL
                )
                """
            )

            con.execute(
                """
                INSERT INTO llm_usage (
                    model,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost_usd
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    model,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost_usd,
                ),
            )

    finally:
        con.close()


def get_llm_usage(db_path: str) -> dict:
    """Return total and per-request LLM usage."""

    con = connect(db_path)

    try:
        with con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    model TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    estimated_cost_usd REAL
                )
                """
            )

        rows = con.execute(
            """
            SELECT
                id,
                created_at,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                estimated_cost_usd
            FROM llm_usage
            ORDER BY id DESC
            LIMIT 500
            """
        ).fetchall()

        totals = con.execute(
            """
            SELECT
                COUNT(*) AS request_count,
                SUM(input_tokens) AS input_tokens,
                SUM(output_tokens) AS output_tokens,
                SUM(total_tokens) AS total_tokens,
                SUM(estimated_cost_usd) AS estimated_cost_usd
            FROM llm_usage
            """
        ).fetchone()

        return {
            "totals": dict(totals),
            "requests": [dict(row) for row in rows],
        }

    finally:
        con.close()

def init_db(path: str) -> None:
    con = connect(path)
    with con:
        con.executescript(SCHEMA)
    con.close()
