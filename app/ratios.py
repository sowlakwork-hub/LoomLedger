"""All arithmetic lives here. The LLM never calculates."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    company: str
    fiscal_year: int
    basis: str
    metric: str
    value: float
    source_file: str
    page_no: int
    unit: str = "INR_crore"


@dataclass(frozen=True)
class RatioResult:
    name: str
    value: float
    inputs: tuple[Fact, ...]

    @property
    def pages(self) -> list[tuple[str, int]]:
        return [(f.source_file, f.page_no) for f in self.inputs]


# name -> (input metrics, formula over those inputs, unit)
RATIOS = {
    "net_margin_pct": (("net_profit", "revenue"), lambda v: v[0] / v[1] * 100, "%"),
    "ebitda_margin_pct": (
        ("pbt", "finance_cost", "depreciation", "revenue"),
        lambda v: (v[0] + v[1] + v[2]) / v[3] * 100,
        "%",
    ),
    "debt_to_equity": (
        ("borrowings_lt", "borrowings_st", "equity"),
        lambda v: (v[0] + v[1]) / v[2],
        "x",
    ),
    "interest_cover": (("pbt", "finance_cost"), lambda v: (v[0] + v[1]) / v[1], "x"),
    "materials_cost_pct_revenue": (("materials_cost", "revenue"), lambda v: v[0] / v[1] * 100, "%"),
}
DENOMINATORS = {  # input position that must be non-zero
    "net_margin_pct": 1, "ebitda_margin_pct": 3, "debt_to_equity": 2,
    "interest_cover": 1, "materials_cost_pct_revenue": 1,
}


def compute_ratio(name: str, facts: dict[str, Fact]) -> RatioResult:
    if name not in RATIOS:
        raise ValueError(f"Unknown ratio: {name}")
    metrics, fn, _ = RATIOS[name]
    missing = [m for m in metrics if m not in facts]
    if missing:
        raise KeyError(f"Missing facts: {', '.join(missing)}")
    inputs = tuple(facts[m] for m in metrics)
    first = inputs[0]
    for f in inputs[1:]:
        if (f.company, f.fiscal_year, f.basis) != (first.company, first.fiscal_year, first.basis):
            raise ValueError(f"Mismatched company/year/basis in {name}")
    units = {f.unit for f in inputs}
    if "UNKNOWN" in units:
        raise ValueError(f"{name}: source unit is UNKNOWN; verify unit before calculating")
    if len(units) != 1:
        raise ValueError(f"{name}: input units do not match: {sorted(units)}")
    values = [f.value for f in inputs]
    if values[DENOMINATORS[name]] == 0:
        raise ValueError(f"{name}: denominator is zero")
    return RatioResult(name, round(fn(values), 4), inputs)
