"""Safe, read-only SQL execution for the agent."""
import re
import sqlite3

from app.db import connect

ALLOWED_TABLES = {"facts"}
MAX_ROWS = 200
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|vacuum|reindex|load_extension)\b",
    re.I,
)


class UnsafeSQL(ValueError):
    pass


def validate(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise UnsafeSQL("Only one statement allowed")
    if not re.match(r"^(select|with)\b", s, re.I):
        raise UnsafeSQL("Only SELECT allowed")
    if FORBIDDEN.search(s) or "--" in s or "/*" in s:
        raise UnsafeSQL("Forbidden keyword or comment")
    for t in re.findall(r"\b(?:from|join)\s+([A-Za-z_][\w]*)", s, re.I):
        if t.lower() not in ALLOWED_TABLES:
            raise UnsafeSQL(f"Table not allowed: {t}")
    return s


def _authorizer(action, arg1, arg2, dbname, source):
    ok = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION}
    if action in ok:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and arg1 in ALLOWED_TABLES:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def run_readonly(db_path: str, sql: str, max_steps: int = 2_000_000) -> list[dict]:
    s = validate(sql)
    con = connect(db_path, read_only=True)
    try:
        con.set_authorizer(_authorizer)
        steps = {"n": 0}

        def stop():
            steps["n"] += 1
            return 1 if steps["n"] > max_steps // 1000 else 0

        con.set_progress_handler(stop, 1000)
        cur = con.execute(s)
        return [dict(r) for r in cur.fetchmany(MAX_ROWS)]
    except sqlite3.Error as e:
        raise UnsafeSQL(f"Query failed: {e}") from e
    finally:
        con.close()
