"""Import manually verified extraction CSV into LoomLedger facts.

Run from repo root:
python -m app.import_verified data/auto_extraction_v7.csv

Rows with UNKNOWN units are retained but ratio calculations involving them are blocked.
Existing facts are never overwritten; duplicates cause a clear error.
"""
import csv
import sys
from pathlib import Path
from app.config import get_settings
from app.db import connect, init_db

ALIASES = {
    "Ambika Cotton Mills": "ambika_cotton_mills",
    "KPR Mill": "kpr_mill",
    "Lakshmi Machine Works": "lakshmi_machine_works",
    "Precot": "precot",
    "Rajapalayam Mills": "rajapalayam_mills",
}
METRIC_MAP = {"materials_cost": "materials_cost"}

def main(csv_path: str):
    settings = get_settings()
    init_db(settings.db_path)
    con = connect(settings.db_path)
    inserted = 0
    try:
        with con, open(csv_path, newline="", encoding="cp1252") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                if row.get("review_status", "").upper() != "PENDING_REVIEW":
                    raise ValueError("Expected the supplied manually checked candidate file with PENDING_REVIEW markers.")
                company = ALIASES.get(row["company"])
                if not company:
                    raise ValueError(f"Unknown company: {row['company']}")
                metric = METRIC_MAP.get(row["metric"], row["metric"])
                unit = row["unit"].strip() or "UNKNOWN"
                con.execute("""
                    INSERT INTO facts
                    (company,fiscal_year,basis,metric,value,unit,source_file,page_no,
                     extraction_method,needs_review)
                    VALUES (?,?,?,?,?,?,?,?,?,0)
                """, (company, int(row["fiscal_year"]), row["basis"], metric,
                      float(row["value"]), unit, row["source_file"], int(row["page_no"]),
                      row["extraction_method"] + "+manual_verified"))
                inserted += 1
        print(f"Imported {inserted} manually verified facts.")
        print("Rows with UNKNOWN units are retained, but affected ratios will be skipped.")
    finally:
        con.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.import_verified data/auto_extraction_v7.csv")
    main(sys.argv[1])
