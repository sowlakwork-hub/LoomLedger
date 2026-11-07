
from pathlib import Path
import re

import pytest

from app.extract import (
    METRIC_LABELS,
    extract_number_after_label,
    detect_unit,
    extract_pdf_text,
    extract_general_metrics,
    extract_balance_sheet_borrowings,
    process_report,
)


def test_note_number_is_not_used_as_financial_value():
    line = "Revenue from operations 21 82345.99 84750.14"

    assert extract_number_after_label(
        line, METRIC_LABELS["revenue"][0]
    ) == 82345.99


def test_finance_cost_note_number_is_skipped():
    line = "Finance costs 26 1907.05 639.68"

    assert extract_number_after_label(
        line, METRIC_LABELS["finance_cost"][0]
    ) == 1907.05


def test_equity_without_note_number_uses_current_year_value():
    line = "Total Equity 2,871.83 2,662.29 Total Tax expense 48.63 108.50"

    assert extract_number_after_label(
        line, METRIC_LABELS["equity"][0]
    ) == 2871.83


def test_unit_conversion_detection():
    assert detect_unit(
        "STATEMENT OF PROFIT & LOSS (Rs. in Lakhs)"
    ) == "INR_lakhs"

    assert detect_unit(
        "BALANCE SHEET (Rs. in Crores)"
    ) == "INR_crore"


def test_total_equity_does_not_match_total_equity_and_liabilities():
    pattern = re.compile(
        r"\btotal\s+equity\b(?!\s+and\s+liabilities)",
        re.IGNORECASE,
    )

    assert pattern.search(
        "Total Equity (A) 85889.39 81661.54"
    )

    assert not pattern.search(
        "Total Equity and Liabilities (A+B+C) 106947.09 98026.93"
    )


def test_ambika_fy24_extraction():
    pdf = Path("data/raw/ambika_cotton_mills_FY24.pdf")

    if not pdf.exists():
        pytest.skip("Ambika FY24 PDF not available")

    pages = extract_pdf_text(pdf)

    assert pages
    assert all("page_no" in page for page in pages)

    facts = extract_general_metrics(
        pages,
        "Ambika Cotton Mills",
        2024,
        pdf.name,
    )

    assert facts

    by_metric = {fact["metric"]: fact for fact in facts}

    assert "revenue" in by_metric
    assert "net_profit" in by_metric
    assert "pbt" in by_metric
    assert "finance_cost" in by_metric
    assert "depreciation" in by_metric

    assert by_metric["revenue"]["page_no"] > 0


def test_kpr_fy24_extraction():
    pdf = Path("data/raw/kpr_mill_FY24.pdf")

    if not pdf.exists():
        pytest.skip("KPR FY24 PDF not available")

    pages = extract_pdf_text(pdf)

    facts = extract_general_metrics(
        pages,
        "KPR Mill",
        2024,
        pdf.name,
    )

    assert facts

    by_metric = {fact["metric"]: fact for fact in facts}

    assert "revenue" in by_metric
    assert "net_profit" in by_metric
    assert "pbt" in by_metric

    assert by_metric["revenue"]["page_no"] > 0


def test_lakshmi_fy25_extraction():
    pdf = Path("data/raw/lakshmi_machine_works_FY25.pdf")

    if not pdf.exists():
        pytest.skip("Lakshmi FY25 PDF not available")

    pages = extract_pdf_text(pdf)

    facts = extract_general_metrics(
        pages,
        "Lakshmi Machine Works",
        2025,
        pdf.name,
    )

    assert facts

    by_metric = {fact["metric"]: fact for fact in facts}

    assert "revenue" in by_metric
    assert by_metric["revenue"]["page_no"] > 0


def test_pdf_page_numbers_are_preserved():
    pdf = Path("data/raw")

    if not pdf.exists():
        pytest.skip("PDF directory not available")

    pdf_files = list(pdf.glob("*.pdf"))

    if not pdf_files:
        pytest.skip("No PDF files available")

    pages = extract_pdf_text(pdf_files[0])

    assert pages
    assert pages[0]["page_no"] == 1

    for page in pages:
        assert isinstance(page["page_no"], int)
        assert page["page_no"] > 0


def test_extract_number_returns_none_when_label_missing():
    line = "Total expenses 500.00"

    assert extract_number_after_label(
        line, METRIC_LABELS["revenue"][0]
    ) is None
