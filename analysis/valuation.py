"""
Computes EBITDA, enterprise value, and EV/EBITDA multiple from fetched financials.

All functions return None rather than raising when inputs are missing, so the caller
can decide how to handle incomplete data (skip, flag, substitute sector median, etc.).
"""


def compute_ebitda(financials: dict) -> float | None:
    """
    EBITDA = EBIT (operating income) + D&A.

    We add back D&A because it is a non-cash charge that reduces reported earnings
    but does not represent actual cash outflow — EBITDA is therefore a closer proxy
    to operating cash generation than EBIT alone.
    """
    ebit = financials.get("operating_income")
    da = financials.get("depreciation_and_amortisation")

    if ebit is None or da is None:
        return None

    return ebit + da


def compute_enterprise_value(financials: dict) -> float | None:
    """
    EV = Market Cap + Total Debt − Cash.

    Enterprise Value represents the total theoretical acquisition cost: you pay
    market cap for the equity, assume the target's debt, and receive its cash.
    All three inputs must be present; any missing field returns None.
    """
    market_cap = financials.get("market_cap")
    total_debt = financials.get("total_debt")
    cash = financials.get("cash")

    if any(v is None for v in (market_cap, total_debt, cash)):
        return None

    return market_cap + total_debt - cash


def compute_ev_ebitda(ev: float | None, ebitda: float | None) -> float | None:
    """
    EV/EBITDA multiple — the most common relative valuation metric in M&A.

    Rounded to 2 decimal places. Returns None if either input is None or if
    EBITDA is zero (division guard).
    """
    if ev is None or ebitda is None or ebitda == 0:
        return None

    return round(ev / ebitda, 2)


def run_valuation(financials: dict) -> dict:
    """Compute all three valuation metrics in sequence and return a summary dict."""
    ebitda = compute_ebitda(financials)
    ev = compute_enterprise_value(financials)
    ev_ebitda = compute_ev_ebitda(ev, ebitda)

    return {
        "ebitda": ebitda,
        "enterprise_value": ev,
        "ev_ebitda_multiple": ev_ebitda,
    }
