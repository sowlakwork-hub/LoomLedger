from app.agent import answer


def test_ratio_endpoint_has_pages(client):
    r = client.get("/ratio", params={"name": "debt_to_equity", "companies": ["kpr_mill"]})
    pt = r.json()["series"]["kpr_mill"][0]
    assert pt["value"] == 0.5
    assert {p["page"] for p in pt["pages"]} == {50, 51, 49}


def test_limits_and_unknown(client):
    bad_name = client.get("/ratio", params={"name": "nope", "companies": ["a"]})
    assert bad_name.status_code == 400
    too_many = client.get("/ratio", params={"name": "debt_to_equity", "companies": list("abcd")})
    assert too_many.status_code == 400


def test_pdf_traversal_blocked(client):
    assert client.get("/pdf/..%2Fsecret.pdf").status_code == 404


def test_chart_page(client):
    assert "LoomLedger" in client.get("/chart").text


def test_agent_uses_python_for_ratio_and_blocks_bad_sql(db):
    ok = answer(
        "d/e?", db, "k", "m",
        llm=lambda *a: {"ratio": "debt_to_equity", "companies": ["kpr_mill"]},
    )
    assert ok["result"]["series"]["kpr_mill"][0]["value"] == 0.5
    bad = answer("x", db, "k", "m", llm=lambda *a: {"sql": "DROP TABLE facts"})
    assert "error" in bad