"""
Generates plain-English deal risk flags from valuation, DCF, and financial data inputs.

Each flag is a self-contained sentence an analyst can paste directly into a pitch deck.
Flags are additive: all that fire are returned together in a list.
"""

from analysis.valuation import compute_ebitda


def generate_risk_flags(
    acquirer_data: dict,
    target_data: dict,
    valuation: dict,
    dcf: dict,
) -> list:
    """
    Run six financial-logic checks and return a list of plain-English risk flag strings.

    Returns an empty list when no flags fire (clean deal profile).
    """
    flags = []

    # 1. Elevated trading multiple
    # EV/EBITDA > 15x is historically associated with expensive deals where synergy
    # realisation is needed just to break even on the acquisition price.
    ev_ebitda = valuation.get("ev_ebitda_multiple")
    if ev_ebitda is not None and ev_ebitda > 15:
        flags.append(
            f"Target trades at elevated multiple ({ev_ebitda:.1f}x EV/EBITDA) "
            "-- deal may be expensive"
        )

    # 2. Acquisition premium above typical M&A range
    # Most public deals close at 20-40% premiums. Above 40% the acquirer typically
    # needs very large synergies to justify the price paid.
    premium_pct = dcf.get("premium_pct")
    if premium_pct is not None and premium_pct > 40:
        flags.append(
            f"Premium exceeds typical M&A range (20-40%) -- DCF-implied premium is {premium_pct:.1f}%"
        )

    # 3. Acquirer leverage
    # Debt-to-EBITDA > 3x signals a stretched balance sheet that may constrain the
    # acquirer's ability to finance the deal with debt (credit markets typically balk
    # at pro-forma leverage above 4-5x for leveraged buyout-style structures).
    acquirer_ebitda = compute_ebitda(acquirer_data)
    acquirer_debt = acquirer_data.get("total_debt")
    if acquirer_ebitda and acquirer_debt and acquirer_ebitda > 0:
        leverage = acquirer_debt / acquirer_ebitda
        if leverage > 3:
            flags.append(
                f"Acquirer leverage is {leverage:.1f}x Debt/EBITDA "
                "-- may constrain deal financing"
            )

    # 4. Target unprofitability
    # A loss-making target elevates integration risk: the acquirer must fund losses
    # while simultaneously executing an integration, compressing the synergy runway.
    target_net_income = target_data.get("net_income")
    if target_net_income is not None and target_net_income < 0:
        flags.append(
            "Target is unprofitable -- integration risk elevated"
        )

    # 5. Tuck-in acquisition (limited synergy scale)
    # When the target's revenue is less than 10% of the acquirer's, cost synergies and
    # cross-sell opportunities are inherently limited in absolute dollar terms, making
    # it harder to justify a large premium.
    acquirer_revenue = acquirer_data.get("revenue")
    target_revenue = target_data.get("revenue")
    if acquirer_revenue and target_revenue and acquirer_revenue > 0:
        size_ratio = target_revenue / acquirer_revenue
        if size_ratio < 0.10:
            flags.append(
                f"Target revenue is {size_ratio * 100:.1f}% of acquirer revenue "
                "-- tuck-in acquisition with limited synergy scale"
            )

    # 6. Target overvalued vs DCF
    # If the DCF implied price is below the current market price, the model suggests
    # the market is pricing in more value than the fundamentals support -- the acquirer
    # would be buying above intrinsic value even before a control premium.
    implied_price = dcf.get("implied_share_price")
    current_price = target_data.get("current_price")
    if implied_price is not None and current_price is not None:
        if implied_price < current_price:
            flags.append(
                "DCF suggests target is overvalued at current price "
                f"(implied ${implied_price:.2f} vs market ${current_price:.2f})"
            )

    return flags


def apply_sector_flags(target_data: dict, flags: list) -> list:
    """
    Extend the flags list with sector-specific checks for financial-sector targets.

    Standard DCF and EV/EBITDA metrics are less meaningful for banks and financial
    institutions: they carry regulatory capital constraints, mark-to-market balance
    sheets, and are better valued on P/B and ROE frameworks. This function mirrors
    the sector-aware flag pattern from BriefOS and appends finance-specific checks
    only when the target operates in the relevant sector.
    """
    sector = target_data.get("sector", "")

    # Only apply these checks for financial-sector companies.
    if sector not in ("Financial Services", "Banks"):
        return flags

    # 1. Weak return on equity
    # For a bank or financial institution, ROE < 8% signals that the business is not
    # generating adequate returns relative to its equity base -- typically a sign of
    # poor asset quality, excess capital, or structural cost inefficiency.
    roe = target_data.get("returnOnEquity")  # yfinance surfaces this in .info
    if roe is not None:
        if roe < 0.08:
            flags.append(
                f"Target ROE is {roe * 100:.1f}% -- below 8% threshold, "
                "indicating weak profitability for a financial institution"
            )
    else:
        # ROE not available -- may still be calculable manually from financials.
        flags.append("Target ROE unavailable -- verify manually for a financial-sector target")

    # 2. P/B ratio availability check
    # Price-to-Book is the primary relative valuation metric for financials, but
    # yfinance does not always expose book value directly in .info. Flag when it
    # cannot be confirmed so the analyst knows to source it from the 10-K or Bloomberg.
    market_cap = target_data.get("market_cap")
    book_value = target_data.get("bookValue")  # yfinance key in .info, per-share figure

    if market_cap is None or book_value is None:
        flags.append(
            "P/B ratio unavailable -- standard data gap for financials, verify manually"
        )

    return flags
