"""
Fetches income statement, balance sheet, and market data for a given ticker via yfinance.

All functions return snake_case dicts with None for any field yfinance cannot supply,
so downstream code never needs to handle KeyError — just check for None.
"""

import yfinance as yf


def fetch_financials(ticker: str) -> dict:
    """Pull key financial fields for a single ticker and return a clean dict."""

    t = yf.Ticker(ticker)

    # .info holds most snapshot/market-data fields (live quote, market cap, etc.)
    info = t.info

    # Annual income statement — rows are metrics, columns are fiscal year-end dates.
    # .iloc[:, 0] grabs the most recent annual column.
    try:
        income_stmt = t.income_stmt
        # EBIT (operating income) sits under "EBIT" in yfinance's normalised schema.
        operating_income = (
            float(income_stmt.loc["EBIT"].iloc[0])
            if "EBIT" in income_stmt.index
            else None
        )
        # Total revenue for the most recent fiscal year.
        revenue = (
            float(income_stmt.loc["Total Revenue"].iloc[0])
            if "Total Revenue" in income_stmt.index
            else None
        )
        # Net income attributable to common shareholders.
        net_income = (
            float(income_stmt.loc["Net Income"].iloc[0])
            if "Net Income" in income_stmt.index
            else None
        )
    except Exception:
        operating_income = revenue = net_income = None

    # Annual cash flow statement — D&A is a non-cash add-back reported here.
    try:
        cashflow = t.cash_flow
        # yfinance labels this "Depreciation And Amortization" in normalised statements.
        depreciation_and_amortisation = (
            float(cashflow.loc["Depreciation And Amortization"].iloc[0])
            if "Depreciation And Amortization" in cashflow.index
            else None
        )
    except Exception:
        depreciation_and_amortisation = None

    return {
        # Company identity
        "ticker": ticker.upper(),
        "company_name": info.get("longName"),

        # Market data (live / most recent close)
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),

        # Balance sheet items
        # totalDebt includes both short-term and long-term debt obligations.
        "total_debt": info.get("totalDebt"),
        # totalCash is cash + short-term investments — used to net against debt for EV.
        "cash": info.get("totalCash"),

        # Income statement (most recent annual)
        "operating_income": operating_income,
        "revenue": revenue,
        "net_income": net_income,

        # Cash flow statement (most recent annual)
        "depreciation_and_amortisation": depreciation_and_amortisation,

        # Sector — used by sector-aware risk flag logic downstream.
        "sector": info.get("sector"),
    }


def fetch_both(acquirer_ticker: str, target_ticker: str) -> tuple:
    """Fetch financials for both companies and return (acquirer_data, target_data)."""
    acquirer_data = fetch_financials(acquirer_ticker)
    target_data = fetch_financials(target_ticker)
    return acquirer_data, target_data
