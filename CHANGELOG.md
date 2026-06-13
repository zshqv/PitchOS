# Changelog

All notable changes to PitchOS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] -- 2026-06-13

### Added

- **CLI entry point** (`main.py`) with `--acquirer`, `--target`, and `--output` arguments; prints a startup banner and echoes arguments before running the pipeline
- **yfinance data fetcher** (`data/fetcher.py`) with `fetch_financials()` and `fetch_both()`; graceful `None` fallbacks for all twelve fields including operating income, D&A, revenue, net income, and shares outstanding
- **Valuation engine** (`analysis/valuation.py`) computing EBITDA, enterprise value (market cap + debt - cash), and EV/EBITDA multiple; all functions return `None` rather than raising on missing data
- **Five-year DCF engine** (`analysis/dcf.py`) with:
  - `project_free_cash_flows()` -- revenue-growth-driven FCF projection using EBITDA x 0.65 after-tax proxy
  - `compute_terminal_value()` -- Gordon Growth Model terminal value
  - `compute_dcf_equity_value()` -- WACC discounting, equity bridge, and implied share price
  - `compute_acquisition_premium()` -- compares DCF implied price to current market price and flags deals outside the typical 20-40% premium range
- **Deal risk flag engine** (`analysis/risk_flags.py`) with six automated checks:
  1. EV/EBITDA > 15x (elevated multiple)
  2. Acquisition premium > 40% (above typical M&A range)
  3. Acquirer debt > 3x EBITDA (leverage constraint)
  4. Target net income < 0 (unprofitability / integration risk)
  5. Target revenue < 10% of acquirer (tuck-in / limited synergy scale)
  6. DCF implied price < current price (overvaluation signal)
- **Sector-aware risk flags** (`analysis/risk_flags.py`) for financial-institution targets: ROE < 8% check and P/B availability warning, mirroring the sector-aware pattern from BriefOS
- **A4 PDF output engine** (`output/pdf_builder.py`) with five structured sections:
  - Company Snapshots (acquirer and target side-by-side)
  - Valuation Bridge (EV/EBITDA table with commentary)
  - DCF Summary (FCF table, colour-coded premium box, interpretation line)
  - M&A Rationale Summary (plain-English four-sentence deal brief with analyst recommendation)
  - Automated Deal Risk Flags (amber-bulleted list or green all-clear)
- **Analyst-adjustable assumptions** (`config/assumptions.py`) -- `DEFAULT_ASSUMPTIONS` dict with `revenue_growth_rate`, `ebitda_margin`, `wacc`, `terminal_growth_rate`, `projection_years`; imported everywhere, never hardcoded

### Fixed

- ASCII-only text in PDF output (fpdf2 built-in Helvetica font is Latin-1 only; em-dashes and arrows replaced with ASCII equivalents)
- Requirements pinned to versions with pre-built wheels for Python 3.14 (`pandas==3.0.3`, `yfinance==1.3.0`, `fpdf2==2.8.7`, `requests==2.34.2`)
- Graceful exit with clear error message when target ticker is delisted or returns no yfinance data
