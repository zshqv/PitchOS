# PitchOS

PitchOS is a Python CLI tool that generates M&A pitch analysis reports as PDFs.

## Usage

```bash
python main.py --acquirer <ACQUIRER_TICKER> --target <TARGET_TICKER> [--output report.pdf]
```

## Modules

- `data/fetcher.py` — pulls financial data via yfinance
- `analysis/valuation.py` — computes EBITDA, EV, and EV/EBITDA multiples
- `analysis/dcf.py` — DCF engine with terminal value and implied share price
- `analysis/risk_flags.py` — generates plain-English deal risk flags
- `config/assumptions.py` — analyst-adjustable growth rate and WACC inputs
- `output/pdf_builder.py` — renders the final PDF report
