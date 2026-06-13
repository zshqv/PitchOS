"""
Analyst-adjustable inputs for the PitchOS DCF and valuation engine.

ALL numeric assumptions consumed by analysis/ modules must be imported from this file.
Do not hardcode rates or multiples anywhere else in the codebase — change them here and
the entire pipeline updates automatically.

Keys and what they represent
─────────────────────────────
revenue_growth_rate   YoY top-line growth applied to each projection year (decimal).
                      0.05 = 5% growth; calibrate to sector/consensus estimates.

ebitda_margin         EBITDA as a fraction of revenue used for FCF projection (decimal).
                      0.20 = 20% margin; adjust to target's trailing or normalised margin.

wacc                  Weighted Average Cost of Capital — the discount rate applied to
                      projected FCFs and terminal value (decimal). Reflects the blended
                      cost of equity and debt financing for a typical deal in this sector.

terminal_growth_rate  Perpetuity growth rate (Gordon Growth Model) applied after the
                      explicit projection period (decimal). Should be ≤ long-run nominal
                      GDP growth (~2–3%) to avoid implying the company outgrows the economy.

projection_years      Number of years of explicit FCF projection before the terminal value.
                      5 years is the standard in investment-banking practice.
"""

DEFAULT_ASSUMPTIONS: dict = {
    "revenue_growth_rate": 0.05,     # 5% YoY top-line growth
    "ebitda_margin": 0.20,           # 20% EBITDA margin
    "wacc": 0.09,                    # 9% discount rate
    "terminal_growth_rate": 0.025,   # 2.5% perpetuity growth
    "projection_years": 5,           # 5-year explicit forecast horizon
}
