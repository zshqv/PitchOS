"""
DCF engine: projects free cash flows, computes terminal value, and derives implied share price.

All rate/period inputs are sourced from config.assumptions.DEFAULT_ASSUMPTIONS so that
a single file controls every numeric lever in the model.
"""

from config.assumptions import DEFAULT_ASSUMPTIONS


def project_free_cash_flows(revenue: float, assumptions: dict) -> list:
    """
    Project FCF for each year in the explicit forecast horizon.

    FCF = EBITDA × 0.65

    The 0.65 factor is a simplified after-tax proxy: it approximates the cash available
    to debt and equity holders after a blended ~35% effective tax rate, without requiring
    detailed capex or working-capital schedules. In a full model these would be estimated
    individually; here we keep it parsimonious for a first-pass pitch.
    """
    growth = assumptions.get("revenue_growth_rate", DEFAULT_ASSUMPTIONS["revenue_growth_rate"])
    margin = assumptions.get("ebitda_margin", DEFAULT_ASSUMPTIONS["ebitda_margin"])
    years = int(assumptions.get("projection_years", DEFAULT_ASSUMPTIONS["projection_years"]))

    fcf_list = []
    current_revenue = revenue

    for _ in range(years):
        current_revenue *= 1 + growth          # apply YoY growth to roll revenue forward
        ebitda = current_revenue * margin       # derive EBITDA from margin assumption
        fcf = ebitda * 0.65                    # after-tax FCF proxy (see docstring)
        fcf_list.append(fcf)

    return fcf_list


def compute_terminal_value(final_year_fcf: float, assumptions: dict) -> float:
    """
    Gordon Growth Model terminal value: TV = FCF × (1 + g) / (WACC − g).

    The terminal value captures all value generated beyond the explicit projection period.
    In most DCF models it represents 60–80% of total enterprise value, so the assumptions
    here (g and WACC) are the most sensitive levers in the entire model.
    """
    wacc = assumptions.get("wacc", DEFAULT_ASSUMPTIONS["wacc"])
    g = assumptions.get("terminal_growth_rate", DEFAULT_ASSUMPTIONS["terminal_growth_rate"])

    # Guard: WACC must exceed g or the formula produces a negative/infinite TV.
    if wacc <= g:
        raise ValueError(
            f"WACC ({wacc}) must be greater than terminal growth rate ({g}) "
            "for the Gordon Growth Model to produce a finite result."
        )

    return final_year_fcf * (1 + g) / (wacc - g)


def compute_dcf_equity_value(
    fcf_list: list,
    terminal_value: float,
    assumptions: dict,
    net_debt: float,
    shares_outstanding: float,
) -> dict:
    """
    Discount all projected FCFs and the terminal value at WACC, then bridge to equity.

    Equity Value = Enterprise Value (DCF) − Net Debt
    Implied Share Price = Equity Value / Shares Outstanding

    Net debt = total_debt − cash (passed in from fetched financials so this function
    stays pure and testable without needing the full financials dict).
    """
    wacc = assumptions.get("wacc", DEFAULT_ASSUMPTIONS["wacc"])

    # Present value of each projected FCF: PV = FCF_t / (1 + WACC)^t
    total_pv_fcf = sum(
        fcf / (1 + wacc) ** (t + 1)
        for t, fcf in enumerate(fcf_list)
    )

    # Terminal value is received at the end of year N, so discount back N periods.
    n = len(fcf_list)
    pv_terminal_value = terminal_value / (1 + wacc) ** n

    enterprise_value_dcf = total_pv_fcf + pv_terminal_value

    # Bridge from enterprise value to equity value by subtracting net financial debt.
    equity_value = enterprise_value_dcf - net_debt

    # Implied price per share — the DCF's bottom-line output.
    implied_share_price = (
        equity_value / shares_outstanding if shares_outstanding else None
    )

    return {
        "total_pv_fcf": round(total_pv_fcf, 2),
        "pv_terminal_value": round(pv_terminal_value, 2),
        "enterprise_value_dcf": round(enterprise_value_dcf, 2),
        "equity_value": round(equity_value, 2),
        "implied_share_price": round(implied_share_price, 2) if implied_share_price is not None else None,
    }


def run_dcf(financials: dict, assumptions: dict | None = None) -> dict:
    """Orchestrate the full DCF pipeline for a single company's financials dict."""
    if assumptions is None:
        assumptions = DEFAULT_ASSUMPTIONS

    revenue = financials.get("revenue")
    shares = financials.get("shares_outstanding")
    total_debt = financials.get("total_debt") or 0
    cash = financials.get("cash") or 0
    net_debt = total_debt - cash

    if revenue is None:
        return {
            "total_pv_fcf": None,
            "pv_terminal_value": None,
            "enterprise_value_dcf": None,
            "equity_value": None,
            "implied_share_price": None,
        }

    fcf_list = project_free_cash_flows(revenue, assumptions)
    terminal_value = compute_terminal_value(fcf_list[-1], assumptions)
    result = compute_dcf_equity_value(fcf_list, terminal_value, assumptions, net_debt, shares)

    return result


def compute_acquisition_premium(current_price: float, implied_price: float) -> dict:
    """
    Compare the DCF-implied share price to the current market price.

    M&A deals historically close at 20–40% premiums to the target's unaffected share
    price (i.e. the price before deal rumours). This function flags whether the DCF
    implied price supports a premium in that range, is above it (potentially overpaying),
    or is actually a discount (deal destroys acquirer value at current market price).

    A positive premium_pct means the DCF implies more value than the market currently
    prices in — consistent with a credible acquisition rationale.
    A negative premium_pct means the market already prices in more value than the DCF
    supports — the acquirer would be paying above intrinsic value.
    """
    if current_price is None or implied_price is None or current_price == 0:
        return {
            "premium_pct": None,
            "is_accretive": None,
            "label": "Unavailable",
        }

    premium_pct = round(((implied_price - current_price) / current_price) * 100, 1)
    is_accretive = implied_price > current_price
    label = "Premium" if is_accretive else "Discount"

    return {
        "premium_pct": premium_pct,
        "is_accretive": is_accretive,
        "label": label,
    }
