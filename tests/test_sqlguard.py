import pytest

from app.sqlguard import UnsafeSQL, run_readonly


@pytest.mark.parametrize("sql", [
    "DELETE FROM facts", "SELECT 1; DROP TABLE facts", "SELECT * FROM pages",
    "PRAGMA table_info(facts)", "SELECT * FROM facts -- x", "WITH a AS (SELECT 1) DELETE FROM facts",
    "SELECT * FROM sqlite_master",
])
def test_blocked(db, sql):
    with pytest.raises(UnsafeSQL):
        run_readonly(db, sql)


def test_select_ok(db):
    rows = run_readonly(db, "SELECT metric, value, page_no FROM facts WHERE metric='revenue';")
    assert rows == [{"metric": "revenue", "value": 1000.0, "page_no": 40}]
