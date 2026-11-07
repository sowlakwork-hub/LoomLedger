import pytest
from app.ratios import Fact, compute_ratio

def fact(metric, value, page, unit):
    return Fact("kpr_mill", 2025, "standalone", metric, value, "report.pdf", page, unit)

def test_ratio_rejects_unknown_units():
    facts = {
        "net_profit": fact("net_profit", 100, 10, "UNKNOWN"),
        "revenue": fact("revenue", 1000, 11, "UNKNOWN"),
    }
    with pytest.raises(ValueError, match="UNKNOWN"):
        compute_ratio("net_margin_pct", facts)

def test_ratio_rejects_mixed_units():
    facts = {
        "net_profit": fact("net_profit", 100, 10, "INR_lakhs"),
        "revenue": fact("revenue", 1000, 11, "INR_crore"),
    }
    with pytest.raises(ValueError, match="do not match"):
        compute_ratio("net_margin_pct", facts)

def test_ratio_accepts_matching_units_and_keeps_pages():
    facts = {
        "net_profit": fact("net_profit", 100, 10, "INR_lakhs"),
        "revenue": fact("revenue", 1000, 11, "INR_lakhs"),
    }
    result = compute_ratio("net_margin_pct", facts)
    assert result.value == 10.0
    assert result.pages == [("report.pdf", 10), ("report.pdf", 11)]
