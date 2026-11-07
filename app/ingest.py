"""Usage:
  python -m app.ingest scan data/raw        # store page text + write data/candidates.csv
  python -m app.ingest load data/candidates.csv   # load rows you reviewed into facts
File naming: <company>_FY<yy>.pdf  e.g. kpr_mill_FY25.pdf  (add _consolidated for consolidated reports).
Candidates are suggestions only: check each against the PDF page, fix, delete wrong rows, then load.
"""
import csv
import re
import sys
from pathlib import Path

from app.config import get_settings
from app.db import connect, init_db

NUM = r"\(?-?[\d,]+\.?\d*\)?"
PATTERNS = {
    "revenue": r"revenue from operations",
    "net_profit": r"profit (?:for the (?:year|period)|after tax)",
    "pbt": r"profit before (?:exceptional items and )?tax",
    "finance_cost": r"finance costs?",
    "depreciation": r"depreciation and amortisation? expenses?",
    "borrowings_lt": r"borrowings",
    "borrowings_st": r"short[- ]term borrowings|current maturities",
    "equity": r"total equity",
    "cotton_cost": r"cost of materials consumed",
}
NAME_RE = re.compile(r"^(?P<co>.+)_FY(?P<yy>\d{2})(?:_(?P<basis>consolidated|standalone))?\.pdf$", re.I)


def parse_name(p: Path) -> tuple[str, int, str]:
    m = NAME_RE.match(p.name)
    if not m:
        raise ValueError(f"Bad filename: {p.name}")
    return m["co"].lower(), 2000 + int(m["yy"]), (m["basis"] or "standalone").lower()


def to_num(tok: str) -> float:
    neg = tok.startswith("(") or tok.startswith("-")
    v = float(re.sub(r"[^\d.]", "", tok) or 0)
    return -v if neg else v


def candidates(text: str):
    for line in text.splitlines():
        for metric, pat in PATTERNS.items():
            m = re.search(pat, line, re.I)
            if m:
                nums = [n for n in re.findall(NUM, line[m.end():]) if re.search(r"\d", n)]
                if nums:
                    yield metric, to_num(nums[0]), line.strip()


def scan(raw_dir: str) -> None:
    import pdfplumber  # lazy: only needed for ingestion

    s = get_settings()
    init_db(s.db_path)
    con = connect(s.db_path)
    out = Path("data/candidates.csv")
    with out.open("w", newline="", encoding="utf-8") as fh, con:
        w = csv.writer(fh)
        w.writerow(["company", "fiscal_year", "basis", "metric", "value", "source_file", "page_no", "line"])
        for pdf in sorted(Path(raw_dir).glob("*.pdf")):
            co, fy, basis = parse_name(pdf)
            with pdfplumber.open(pdf) as doc:
                for i, page in enumerate(doc.pages, start=1):
                    text = page.extract_text() or ""
                    con.execute("INSERT OR REPLACE INTO pages VALUES (?,?,?)", (pdf.name, i, text))
                    for metric, val, line in candidates(text):
                        w.writerow([co, fy, basis, metric, val, pdf.name, i, line])
            print("scanned", pdf.name)
    print("Review", out)


def load(csv_path: str) -> None:
    s = get_settings()
    init_db(s.db_path)
    con = connect(s.db_path)
    n = 0
    with con, open(csv_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            con.execute(
                "INSERT OR REPLACE INTO facts (company,fiscal_year,basis,metric,value,source_file,page_no,"
                "extraction_method) VALUES (?,?,?,?,?,?,?,?)",
                (r["company"], int(r["fiscal_year"]), r["basis"], r["metric"], float(r["value"]),
                 r["source_file"], int(r["page_no"]), "pdfplumber+manual_review"),
            )
            n += 1
    print("loaded", n, "facts")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("scan", "load"):
        sys.exit(__doc__)
    (scan if sys.argv[1] == "scan" else load)(sys.argv[2])
