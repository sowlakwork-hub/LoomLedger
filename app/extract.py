
"""
LOOMLEDGER - HYBRID ANNUAL REPORT EXTRACTOR
Version: 3.0-HYBRID (minimal targeted corrections)

Features:
1. PDF text extraction using pdfplumber.
2. Financial statement extraction.
3. Notes to Financial Statements extraction.
4. Section-aware borrowing extraction.
5. Targeted OCR fallback using Tesseract.
6. Original PDF page number tracking.
7. Candidate CSV and report status CSV.
8. No automatic SQLite insertion.

All extracted values remain PENDING_REVIEW.
"""

import argparse
import csv
import re
import shutil
from pathlib import Path

import pdfplumber

try:
    import fitz
except ImportError:
    fitz = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None


# =========================================================
# 1. CONFIGURATION
# =========================================================

TESSERACT_PATH = (
    shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
if pytesseract is not None:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

DEFAULT_DPI = 300
MIN_TEXT_LENGTH = 80

REQUIRED_METRICS = [
    "revenue",
    "net_profit",
    "pbt",
    "finance_cost",
    "depreciation",
    "materials_cost",
    "equity",
    "borrowings_lt",
    "borrowings_st",
]

METRIC_LABELS = {
    "revenue": [
        r"revenue\s+from\s+operations",
    ],
    "net_profit": [
        # Prefer the final annual result when continuing/discontinued
        # operations are both reported (e.g. Precot).
        r"profit\s+for\s+the\s+(?:year|period)\s*\([^)]*\)",
        r"profit\s*/\s*\(?loss\)?\s+for\s+the\s+(?:year|period)",
        r"profit\s+after\s+tax\s+from\s+continuing\s+operations\s+for\s+the\s+(?:year|period)",
        r"profit\s+for\s+the\s+(?:year|period)",
        r"profit\s+after\s+tax",
        r"net\s+profit",
    ],
    "pbt": [
        r"profit\s*/\s*\(?loss\)?\s+before\s+tax\s*\(\s*v\s*\+\s*vi\s*\)",
        r"profit\s+before\s+tax\s+after\s+exceptional\s+items",
        r"profit\s+before\s+tax\s+from\s+continuing\s+operations",
        r"profit\s+before\s+exceptional\s+items\s+and\s+tax",
        r"profit\s+before\s+tax",
    ],
    "finance_cost": [
        r"finance\s+costs?",
    ],
    "depreciation": [
        r"depreciation\s+and\s+amortisation\s+expenses?",
        r"depreciation\s+and\s+amortization\s+expenses?",
        r"depreciation\s+expenses?",
    ],
    "materials_cost": [
        r"cost\s+of\s+materials\s+consumed",
    ],
    "equity": [
        r"total\s+equity",
    ],
}

COMPANY_ALIASES = {
    "kpr": "KPR Mill",
    "kpr_mill": "KPR Mill",
    "kpr_mills": "KPR Mill",
    "lakshmi_machine_works": "Lakshmi Machine Works",
    "lmw": "Lakshmi Machine Works",
    "rajapalayam_mills": "Rajapalayam Mills",
    "rajapalayam": "Rajapalayam Mills",
    "ambika_cotton_mills": "Ambika Cotton Mills",
    "ambika": "Ambika Cotton Mills",
    "precot": "Precot",
}


# =========================================================
# 2. GENERAL HELPERS
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


def normalize_number(value):
    if value is None:
        return None

    value = value.strip()

    if value in {"-", "--", "—", "–", ""}:
        return None

    negative = value.startswith("(") and value.endswith(")")

    value = value.replace(",", "")
    value = value.replace("(", "")
    value = value.replace(")", "")
    value = value.replace(" ", "")

    try:
        number = float(value)

        if negative:
            number = -abs(number)

        return number

    except ValueError:
        return None


NUMBER_PATTERN = re.compile(
    r"\(?-?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?\)?"
    r"|\(?-?\d+(?:\.\d+)?\)?"
)


def numbers_in_text(text):
    return [
        normalize_number(item)
        for item in NUMBER_PATTERN.findall(text)
        if normalize_number(item) is not None
    ]


def detect_unit(text):
    low = text.lower()

    if "in lakhs" in low or "rs. in lakhs" in low:
        return "INR_lakhs"

    if "in crores" in low or "rs. in crores" in low:
        return "INR_crore"

    if "in thousands" in low:
        return "INR_thousands"

    if "in rupees" in low:
        return "INR"

    return "UNKNOWN"


def detect_basis(text):
    low = text.lower()

    if "consolidated statement" in low:
        return "consolidated"

    if "standalone statement" in low:
        return "standalone"

    if "consolidated financial statements" in low:
        return "consolidated"

    if "standalone financial statements" in low:
        return "standalone"

    return "standalone"


def parse_report_name(pdf_path):
    filename = pdf_path.stem.lower()

    year_match = re.search(
        r"20(24|25|26)|fy[_ -]?(24|25|26)",
        filename,
    )

    fiscal_year = None

    if year_match:
        digits = re.findall(
            r"20\d{2}|24|25|26",
            year_match.group(),
        )

        if digits:
            year = digits[0]

            fiscal_year = (
                int(year)
                if len(year) == 4
                else 2000 + int(year)
            )

    company = None

    for alias, official_name in COMPANY_ALIASES.items():
        if alias in filename:
            company = official_name
            break

    if company is None:
        company = pdf_path.stem.replace("_", " ").title()

    return company, fiscal_year


# =========================================================
# 3. PDF TEXT EXTRACTION
# =========================================================

def extract_pdf_text(pdf_path):
    pages = []

    with pdfplumber.open(pdf_path) as pdf:

        for index, page in enumerate(pdf.pages):

            text = clean_text(
                page.extract_text() or ""
            )

            pages.append({
                "page_no": index + 1,
                "text": text,
                "extraction_method": "pdfplumber",
            })

    return pages


# =========================================================
# 4. BASIC METRIC EXTRACTION
# =========================================================

def extract_number_after_label(line, pattern):
    """Extract current-year amount after a label, skipping note references.

    Example: Revenue from operations 21 82,345.99 84,750.14
    Here 21 is the note number, not the financial amount.
    """
    match = re.search(pattern, line, flags=re.IGNORECASE)
    if not match:
        return None

    values = numbers_in_text(line[match.end():])
    if not values:
        return None

    # A note reference is typically a small integer followed by the
    # current-year and prior-year amounts. Skip only in that pattern.
    if (len(values) >= 3 and values[0].is_integer()
            and 1 <= abs(values[0]) <= 99):
        return values[1]

    return values[0]


def extract_metric_from_page(page_text, metric):
    patterns = METRIC_LABELS.get(metric, [])
    candidates = []

    for line in page_text.splitlines():
        line = clean_text(line)
        if not line:
            continue
        low = line.lower()

        for pattern_index, pattern in enumerate(patterns):
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if not match:
                continue

            # Do not use intermediate continuing-operation profit when
            # a final profit-for-year row is available.
            if metric == "net_profit":
                if any(term in low for term in (
                    "before share", "before exceptional",
                    "profit before tax", "total comprehensive"
                )):
                    continue
                if "profit after tax from continuing operations" in low:
                    score = 80
                elif "profit for the year" in low or "profit / (loss) for the year" in low:
                    score = 100
                else:
                    score = 60
            elif metric == "pbt":
                if "before exceptional items and tax" in low:
                    score = 80
                elif "before tax after exceptional items" in low:
                    score = 100
                elif "before tax (v+vi)" in low or "before tax (v + vi)" in low:
                    score = 110
                elif "before tax from continuing operations" in low:
                    score = 90
                else:
                    score = 50
            else:
                score = 50 - pattern_index

            value = extract_number_after_label(line, pattern)
            if value is not None:
                candidates.append((score, value, line))
            break

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    score, value, line = candidates[0]
    return {"value": value, "matched_line": line, "match_score": score}


def make_fact(
    company,
    fiscal_year,
    metric,
    value,
    unit,
    source_file,
    page_no,
    extraction_method,
    matched_text,
    basis="standalone",
    note="",
):
    return {
        "company": company,
        "fiscal_year": fiscal_year,
        "basis": basis,
        "metric": metric,
        "value": value,
        "unit": unit,
        "source_file": source_file,
        "page_no": page_no,
        "extraction_method": extraction_method,
        "matched_text": matched_text,
        "note": note,
        "review_status": "PENDING_REVIEW",
    }


def _is_statement_of_profit_loss(text):
    """Recognise common audited P&L headings without requiring exact wording."""
    first_lines = " ".join(clean_text(text).lower().splitlines()[:8])
    return bool(
        re.search(r"statement\s+of\s+profit", first_lines)
        or re.search(r"statement\s+of\s+profit\s*&\s*loss", first_lines)
        or re.search(r"profit\s+and\s+loss\s+for\s+the\s+year", first_lines)
    )


def _is_consolidated_page(text):
    return bool(re.search(r"\bconsolidated\b", text, flags=re.IGNORECASE))


def extract_general_metrics(
    pages,
    company,
    fiscal_year,
    source_file,
):
    facts = []

    for metric in METRIC_LABELS:
        candidates = []
        for page in pages:
            text = page["text"]
            if not text:
                continue
            # Keep consolidated data out when the report contains separate
            # standalone statements. Other Version 3.0 fallback pages remain
            # eligible if no standalone statement row is found.
            if _is_consolidated_page(text):
                continue
            result = extract_metric_from_page(text, metric)
            if result is None:
                continue
            statement_priority = 100 if _is_statement_of_profit_loss(text) else 0
            candidates.append((statement_priority + result.get("match_score", 0), page, result))

        if not candidates:
            continue
        candidates.sort(key=lambda item: item[0], reverse=True)
        _, page, result = candidates[0]
        text = page["text"]
        facts.append(
            make_fact(
                company=company,
                fiscal_year=fiscal_year,
                metric=metric,
                value=result["value"],
                unit=detect_unit(text),
                source_file=source_file,
                page_no=page["page_no"],
                extraction_method=page["extraction_method"],
                matched_text=result["matched_line"],
                basis=detect_basis(text),
                note="",
            )
        )

    return facts


# =========================================================
# 5. BALANCE SHEET BORROWING EXTRACTION
# =========================================================

def is_noncurrent_heading(line):
    return bool(
        re.search(
            r"non\s*[- ]?\s*current\s+liabilities",
            line,
            flags=re.IGNORECASE,
        )
    )


def is_current_heading(line):
    return bool(
        re.search(
            r"(?<!non[- ])current\s+liabilities",
            line,
            flags=re.IGNORECASE,
        )
    )


def extract_borrowing_row_value(line):
    """Extract current-year borrowing amount, skipping a note number."""
    match = re.search(r"\bborrowings\b", line, flags=re.IGNORECASE)
    if not match:
        return None
    values = numbers_in_text(line[match.end():])
    if not values:
        return None
    if (len(values) >= 3 and values[0].is_integer()
            and 1 <= abs(values[0]) <= 99):
        return values[1]
    return values[0]


def extract_balance_sheet_borrowings(
    pages,
    company,
    fiscal_year,
    source_file,
):
    facts = []

    for page in pages:

        text = page["text"]

        if not text:
            continue

        low = text.lower()

        if "borrowings" not in low:
            continue

        if not (
            "balance sheet" in low
            or "equity and liabilities" in low
        ):
            continue

        section = None
        matches = {
            "borrowings_lt": [],
            "borrowings_st": [],
        }

        for line in text.splitlines():

            line = clean_text(line)

            if is_noncurrent_heading(line):
                section = "noncurrent"
                continue

            if is_current_heading(line):
                section = "current"
                continue

            if section not in {"noncurrent", "current"}:
                continue

            value = extract_borrowing_row_value(line)

            if value is None:
                continue

            metric = (
                "borrowings_lt"
                if section == "noncurrent"
                else "borrowings_st"
            )

            matches[metric].append((value, line))

        unit = detect_unit(text)
        basis = detect_basis(text)

        for metric, rows in matches.items():

            # Avoid choosing ambiguous duplicate rows.
            if len(rows) != 1:
                continue

            value, source_line = rows[0]

            facts.append(
                make_fact(
                    company=company,
                    fiscal_year=fiscal_year,
                    metric=metric,
                    value=value,
                    unit=unit,
                    source_file=source_file,
                    page_no=page["page_no"],
                    extraction_method=page["extraction_method"],
                    matched_text=source_line,
                    basis=basis,
                    note="Extracted from Balance Sheet liability section.",
                )
            )

    return facts


# =========================================================
# 6. NOTES TO FINANCIAL STATEMENTS BORROWING EXTRACTION
# =========================================================

def is_borrowings_note(text):
    """
    Identify a detailed borrowing note.

    Example:
    16. BORROWINGS
    """

    return bool(
        re.search(
            r"(?:\d+[.)]?\s*)?borrowings\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def extract_note_borrowings(
    pages,
    company,
    fiscal_year,
    source_file,
    existing_facts,
):
    """
    Search Notes to Financial Statements for borrowing details.

    Supports notes containing:
    - Secured working-capital loans.
    - Unsecured working-capital loans.
    - Loans repayable on demand.
    - Total borrowing amount.

    It uses the total row when clearly identifiable.
    It does not mistake the individual secured/unsecured
    components for the total.
    """

    facts = list(existing_facts)

    found = {
        fact["metric"]
        for fact in facts
    }

    for page in pages:

        if not is_borrowings_note(page["text"]):
            continue

        text = page["text"]
        lines = text.splitlines()

        unit = detect_unit(text)
        basis = detect_basis(text)

        # Search for working-capital loan components.
        component_values = []

        for line in lines:

            low = line.lower()

            if (
                "loans repayable on demand" in low
                and "working capital" in low
            ):
                values = numbers_in_text(line)

                if values:
                    component_values.append(values[0])

        # Look for an explicit total row.
        total_value = None
        total_line = None

        for line in lines:

            low = line.strip().lower()

            if not low:
                continue

            values = numbers_in_text(line)

            if not values:
                continue

            # A line containing only a total label and values.
            if re.match(r"^total\b", low):

                total_value = values[0]
                total_line = line.strip()
                break

        # If no total label was extracted, use the sum of
        # clearly identified components only when at least
        # two components are present.
        if (
            total_value is None
            and len(component_values) >= 2
        ):
            total_value = sum(component_values)

            total_line = (
                "Sum of identified secured and unsecured "
                "working-capital borrowing components"
            )

        # Working-capital loans repayable on demand are
        # candidates for current borrowings.
        if (
            total_value is not None
            and "borrowings_st" not in found
            and component_values
        ):
            facts.append(
                make_fact(
                    company=company,
                    fiscal_year=fiscal_year,
                    metric="borrowings_st",
                    value=total_value,
                    unit=unit,
                    source_file=source_file,
                    page_no=page["page_no"],
                    extraction_method=page["extraction_method"],
                    matched_text=total_line,
                    basis=basis,
                    note=(
                        "Candidate from Borrowings note. "
                        "Working-capital loans repayable on demand. "
                        "Cross-check against Balance Sheet."
                    ),
                )
            )

            found.add("borrowings_st")

    return facts


def extract_explicit_no_borrowings(
    pages,
    company,
    fiscal_year,
    source_file,
):
    """
    Create zero-value candidates only when the standalone report
    explicitly states that the company has no borrowings.

    Absence of a Balance Sheet borrowing row alone is NOT enough.
    """
    patterns = [
        r"the company does not have any borrowings in its capital portfolio",
        r"the company has not taken any loans or other borrowings from any lender",
        r"the company does not have any external borrowings from banks or any other financial institution",
    ]

    for page in pages:
        page_text = page["text"]
        if not page_text or detect_basis(page_text) != "standalone":
            continue

        for line in page_text.splitlines():
            source_line = clean_text(line)
            if not source_line:
                continue

            if any(
                re.search(pattern, source_line, flags=re.IGNORECASE)
                for pattern in patterns
            ):
                facts = []
                note = (
                    "Zero-value candidate based on an explicit "
                    "company-wide no-borrowings disclosure. "
                    "Human validation required."
                )

                for metric in ("borrowings_lt", "borrowings_st"):
                    facts.append(
                        make_fact(
                            company=company,
                            fiscal_year=fiscal_year,
                            metric=metric,
                            value=0.0,
                            unit=detect_unit(page_text),
                            source_file=source_file,
                            page_no=page["page_no"],
                            extraction_method=page["extraction_method"],
                            matched_text=source_line,
                            basis="standalone",
                            note=note,
                        )
                    )
                return facts

    return []


# =========================================================
# 7. COMBINE EXTRACTION RESULTS
# =========================================================

def combine_facts(*fact_lists):
    """
    Preserve one candidate per metric.

    Priority:
    1. Balance Sheet for borrowings and equity.
    2. Other financial statements for P&L metrics.
    3. Notes as fallback for missing borrowings.
    """

    combined = {}

    for fact_list in fact_lists:

        for fact in fact_list:

            metric = fact["metric"]

            if metric not in combined:
                combined[metric] = fact

    return list(combined.values())


def get_missing_metrics(facts):
    found = {
        fact["metric"]
        for fact in facts
    }

    return [
        metric
        for metric in REQUIRED_METRICS
        if metric not in found
    ]


# =========================================================
# 8. OCR FALLBACK
# =========================================================

def ocr_page(pdf_path, page_index, dpi=DEFAULT_DPI):

    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed.")

    if pytesseract is None or Image is None:
        raise RuntimeError("OCR dependencies are not installed.")

    if not Path(TESSERACT_PATH).exists():
        raise RuntimeError(
            f"Tesseract executable not found: {TESSERACT_PATH}"
        )

    document = fitz.open(pdf_path)

    try:

        page = document.load_page(page_index)

        zoom = dpi / 72

        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom),
            alpha=False,
        )

        image = Image.frombytes(
            "RGB",
            [pixmap.width, pixmap.height],
            pixmap.samples,
        )

        text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 6",
        )

        return clean_text(text)

    finally:
        document.close()


def is_relevant_page(text):
    low = text.lower()

    keywords = [
        "statement of profit",
        "profit and loss",
        "balance sheet",
        "equity and liabilities",
        "borrowings",
        "financial liabilities",
        "revenue from operations",
        "notes to the financial statements",
    ]

    return any(word in low for word in keywords)



def run_targeted_ocr(
    pdf_path,
    pages,
    company,
    fiscal_year,
    source_file,
    existing_facts,
    dpi=DEFAULT_DPI,
):
    """
    OCR ONLY pages with insufficient extracted text.

    Readable pages are never OCRed.
    All readable pages must be searched using text extraction first.
    """

    facts = list(existing_facts)

    missing = get_missing_metrics(facts)

    if not missing:
        print("All required metrics found using text extraction.")
        return facts

    if fitz is None or pytesseract is None or Image is None:
        print("OCR dependencies unavailable.")
        return facts

    print("\nMissing metrics:", ", ".join(missing))
    print("Checking only pages without readable text.")

    unreadable_pages = [
        page for page in pages
        if len(page["text"].strip()) < MIN_TEXT_LENGTH
    ]

    print(
        f"Total pages: {len(pages)} | "
        f"Unreadable pages: {len(unreadable_pages)}"
    )

    if not unreadable_pages:
        print(
            "No unreadable pages available for OCR. "
            "Remaining metrics require improved text extraction "
            "or manual review."
        )
        return facts

    for page in unreadable_pages:

        if not get_missing_metrics(facts):
            break

        print(f"OCR processing page {page['page_no']}")

        try:

            ocr_text = ocr_page(
                pdf_path,
                page["page_no"] - 1,
                dpi,
            )

            if not ocr_text:
                continue

            ocr_page_data = {
                "page_no": page["page_no"],
                "text": ocr_text,
                "extraction_method": "tesseract_ocr",
            }

            general = extract_general_metrics(
                [ocr_page_data],
                company,
                fiscal_year,
                source_file,
            )

            balance = extract_balance_sheet_borrowings(
                [ocr_page_data],
                company,
                fiscal_year,
                source_file,
            )

            note = extract_note_borrowings(
                [ocr_page_data],
                company,
                fiscal_year,
                source_file,
                [],
            )

            facts = combine_facts(
                facts,
                balance,
                general,
                note,
            )

        except Exception as error:
            print(
                f"OCR warning on page "
                f"{page['page_no']}: {error}"
            )

    remaining = get_missing_metrics(facts)

    if remaining:
        print(
            "Still missing after OCR: "
            + ", ".join(remaining)
        )

    return facts



# =========================================================
# 9. REPORT STATUS
# =========================================================

def create_report_status(
    company,
    fiscal_year,
    source_file,
    pages,
    facts,
):
    missing = get_missing_metrics(facts)

    ocr_pages = sorted({
        fact["page_no"]
        for fact in facts
        if fact["extraction_method"] == "tesseract_ocr"
    })

    if not facts:
        status = "MANUAL_REVIEW_REQUIRED"
    else:
        status = "EXTRACTED_REQUIRES_VALIDATION"

    return {
        "company": company,
        "fiscal_year": fiscal_year,
        "source_file": source_file,
        "total_pages": len(pages),
        "ocr_pages_with_extracted_facts": "; ".join(
            map(str, ocr_pages)
        ),
        "metrics_found": len(REQUIRED_METRICS) - len(missing),
        "metrics_expected": len(REQUIRED_METRICS),
        "missing_metrics": "; ".join(missing),
        "status": status,
    }


# =========================================================
# 10. PROCESS ONE REPORT
# =========================================================

def process_report(pdf_path, dpi=DEFAULT_DPI):

    print("\n" + "=" * 65)
    print("PROCESSING:", pdf_path.name)
    print("=" * 65)

    company, fiscal_year = parse_report_name(pdf_path)

    pages = extract_pdf_text(pdf_path)

    print("Total PDF pages:", len(pages))

    readable = sum(
        1
        for page in pages
        if len(page["text"]) >= MIN_TEXT_LENGTH
    )

    print("Pages with readable text:", readable)

    # A. General P&L metrics.
    general_facts = extract_general_metrics(
        pages,
        company,
        fiscal_year,
        pdf_path.name,
    )

    # B. Balance Sheet borrowing and equity.
    balance_facts = extract_balance_sheet_borrowings(
        pages,
        company,
        fiscal_year,
        pdf_path.name,
    )

    # C. Explicit company-wide disclosure that no borrowings exist.
    no_borrowing_facts = extract_explicit_no_borrowings(
        pages,
        company,
        fiscal_year,
        pdf_path.name,
    )

    # D. Detailed borrowing notes.
    note_facts = extract_note_borrowings(
        pages,
        company,
        fiscal_year,
        pdf_path.name,
        balance_facts,
    )

    facts = combine_facts(
        balance_facts,
        general_facts,
        no_borrowing_facts,
        note_facts,
    )

    print(
        "Metrics found using PDF text:",
        len({fact["metric"] for fact in facts}),
        "/",
        len(REQUIRED_METRICS),
    )

    # D. OCR only for remaining missing metrics.
    facts = run_targeted_ocr(
        pdf_path,
        pages,
        company,
        fiscal_year,
        pdf_path.name,
        facts,
        dpi,
    )

    # E. Final status.
    status = create_report_status(
        company,
        fiscal_year,
        pdf_path.name,
        pages,
        facts,
    )

    print("\nFinal metrics:", status["metrics_found"], "/", status["metrics_expected"])

    if status["missing_metrics"]:
        print("Missing:", status["missing_metrics"])

    print("Status:", status["status"])

    return facts, status


# =========================================================
# 11. CSV OUTPUT
# =========================================================

def write_csv(rows, output_path):

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        print("No rows to write:", output_path)
        return

    fieldnames = list(rows[0].keys())

    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    print("Saved:", output_path)


# =========================================================
# 12. PROCESS ALL REPORTS
# =========================================================

def run(
    input_directory,
    output_csv,
    reports_csv,
    dpi=DEFAULT_DPI,
):

    input_directory = Path(input_directory)

    if not input_directory.exists():
        raise FileNotFoundError(
            f"Input directory does not exist: {input_directory}"
        )

    pdf_files = sorted(
        input_directory.glob("*.pdf")
    )

    if not pdf_files:
        print("No PDF files found.")
        return

    all_facts = []
    all_reports = []

    for pdf_path in pdf_files:

        try:

            facts, report_status = process_report(
                pdf_path,
                dpi,
            )

            all_facts.extend(facts)
            all_reports.append(report_status)

        except Exception as error:

            print(
                f"ERROR processing {pdf_path.name}: {error}"
            )

            company, fiscal_year = parse_report_name(
                pdf_path
            )

            all_reports.append({
                "company": company,
                "fiscal_year": fiscal_year,
                "source_file": pdf_path.name,
                "total_pages": 0,
                "ocr_pages_with_extracted_facts": "",
                "metrics_found": 0,
                "metrics_expected": len(REQUIRED_METRICS),
                "missing_metrics": "; ".join(REQUIRED_METRICS),
                "status": "MANUAL_REVIEW_REQUIRED",
            })

    write_csv(
        all_facts,
        output_csv,
    )

    write_csv(
        all_reports,
        reports_csv,
    )

    print("\n" + "=" * 65)
    print("LOOMLEDGER EXTRACTION SUMMARY")
    print("=" * 65)

    print("Reports processed:", len(all_reports))
    print("Candidate facts:", len(all_facts))

    print(
        "Reports requiring validation:",
        sum(
            1 for item in all_reports
            if item["status"] == "EXTRACTED_REQUIRES_VALIDATION"
        ),
    )

    print(
        "Reports requiring manual review:",
        sum(
            1 for item in all_reports
            if item["status"] == "MANUAL_REVIEW_REQUIRED"
        ),
    )

    print("\nExtraction completed.")
    print("SQLite database was NOT modified.")


# =========================================================
# 13. COMMAND LINE
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description="LoomLedger Hybrid Annual Report Extractor"
    )

    parser.add_argument(
        "input_directory",
        help="Directory containing annual report PDFs",
    )

    parser.add_argument(
        "--output",
        default="data/auto_extraction_v7.csv",
    )

    parser.add_argument(
        "--reports-output",
        default="data/report_status_v7.csv",
    )

    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
    )

    args = parser.parse_args()

    run(
        input_directory=args.input_directory,
        output_csv=args.output,
        reports_csv=args.reports_output,
        dpi=args.dpi,
    )


if __name__ == "__main__":
    main()