from app.db import connect
from app.ratios import RATIOS, Fact, compute_ratio


def load_facts(db_path: str, company: str, year: int, basis: str) -> dict[str, Fact]:
    con = connect(db_path, read_only=True)
    try:
        rows = con.execute(
            "SELECT * FROM facts WHERE company=? AND fiscal_year=? AND basis=?",
            (company, year, basis),
        ).fetchall()
    finally:
        con.close()
    return {
        r["metric"]: Fact(r["company"], r["fiscal_year"], r["basis"], r["metric"],
                          r["value"], r["source_file"], r["page_no"], r["unit"])
        for r in rows
    }


def years_for(db_path: str, company: str, basis: str) -> list[int]:
    con = connect(db_path, read_only=True)
    try:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT fiscal_year FROM facts WHERE company=? AND basis=? ORDER BY 1",
            (company, basis))]
    finally:
        con.close()


def ratio_series(db_path: str, ratio: str, companies: list[str], basis: str = "standalone") -> dict:
    if ratio not in RATIOS:
        raise ValueError(f"Unknown ratio: {ratio}")
    out: dict = {"ratio": ratio, "unit": RATIOS[ratio][2], "basis": basis, "series": {}, "gaps": []}
    for c in companies:
        pts = []
        for y in years_for(db_path, c, basis):
            try:
                r = compute_ratio(ratio, load_facts(db_path, c, y, basis))
            except (KeyError, ValueError) as e:
                out["gaps"].append({"company": c, "year": y, "reason": str(e)})
                continue
            pts.append({"year": y, "value": r.value,
                        "pages": [{"file": f, "page": p} for f, p in r.pages]})
        out["series"][c] = pts
    return out
