import pytest

from app.ratios import Fact, compute_ratio


def F(m, v, p, basis="standalone"):
    return Fact("x", 2025, basis, m, v, "x.pdf", p)


def test_net_margin_with_pages():
    facts = {
        "net_profit": F("net_profit", 100, 41),
        "revenue": F("revenue", 1000, 40),
    }
    r = compute_ratio("net_margin_pct", facts)
    assert r.value == 10.0
    assert r.pages == [("x.pdf", 41), ("x.pdf", 40)]


def test_ebitda_margin():
    f = {
        "pbt": F("pbt", 100, 1),
        "finance_cost": F("finance_cost", 20, 2),
        "depreciation": F("depreciation", 30, 3),
        "revenue": F("revenue", 1000, 4),
    }
    assert compute_ratio("ebitda_margin_pct", f).value == 15.0


def test_interest_cover():
    f = {"pbt": F("pbt", 60, 1), "finance_cost": F("finance_cost", 30, 2)}
    assert compute_ratio("interest_cover", f).value == 3.0


def test_mixed_basis_rejected():
    facts = {
        "pbt": F("pbt", 1, 1, "consolidated"),
        "finance_cost": F("finance_cost", 1, 1),
    }
    with pytest.raises(ValueError):
        compute_ratio("interest_cover", facts)


def test_zero_denominator_and_missing():
    zero = {"pbt": F("pbt", 1, 1), "finance_cost": F("finance_cost", 0, 1)}
    with pytest.raises(ValueError):
        compute_ratio("interest_cover", zero)
    with pytest.raises(KeyError):
        compute_ratio("interest_cover", {"pbt": F("pbt", 1, 1)})