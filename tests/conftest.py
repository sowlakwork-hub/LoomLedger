import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import connect, init_db
from app.main import app

ROWS = [  # (company, year, metric, value, page)
    ("kpr_mill", 2025, "revenue", 1000, 40), ("kpr_mill", 2025, "net_profit", 100, 41),
    ("kpr_mill", 2025, "borrowings_lt", 200, 50), ("kpr_mill", 2025, "borrowings_st", 100, 51),
    ("kpr_mill", 2025, "equity", 600, 49),
]


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "t.sqlite")
    init_db(path)
    con = connect(path)
    with con:
        for c, y, m, v, p in ROWS:
            con.execute("INSERT INTO facts (company,fiscal_year,basis,metric,value,source_file,page_no)"
                        " VALUES (?,?,?,?,?,?,?)", (c, y, "standalone", m, v, "kpr_mill_FY25.pdf", p))
    con.close()
    return path


@pytest.fixture
def client(db):
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_name="examate-rag", environment="test", db_path=db, raw_dir="data/raw")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
