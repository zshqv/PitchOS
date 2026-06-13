"""
PitchOS entry point.

Parses CLI arguments (acquirer ticker, target ticker, output PDF filename), then
orchestrates the full pipeline:
  data fetch → valuation → DCF → acquisition premium → risk flags → PDF render.
"""

import argparse
import sys

from data.fetcher import fetch_both
from analysis.valuation import run_valuation
from analysis.dcf import run_dcf, compute_acquisition_premium
from analysis.risk_flags import generate_risk_flags, apply_sector_flags
from output.pdf_builder import build_report


BANNER = """
╔══════════════════════════════════════╗
║           P I T C H  O S            ║
║    M&A Pitch Analysis Generator     ║
╚══════════════════════════════════════╝
"""

# Fields required for a meaningful DCF; missing any of these causes a graceful exit.
_CRITICAL_FIELDS = {
    "revenue":           "annual revenue (needed for DCF projection)",
    "shares_outstanding": "shares outstanding (needed for implied share price)",
    "current_price":     "current stock price (needed for premium calculation)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pitchos",
        description="Generate an M&A pitch analysis PDF for an acquirer/target pair.",
    )
    parser.add_argument(
        "--acquirer",
        required=True,
        metavar="TICKER",
        help="Ticker symbol of the acquiring company (e.g. MSFT)",
    )
    parser.add_argument(
        "--target",
        required=True,
        metavar="TICKER",
        help="Ticker symbol of the target company (e.g. ATVI)",
    )
    parser.add_argument(
        "--output",
        default="pitchos_report.pdf",
        metavar="FILENAME",
        help="Output PDF filename (default: pitchos_report.pdf)",
    )
    return parser.parse_args()


def _validate_or_exit(data: dict, label: str) -> None:
    """Exit with a clear message if any critical field is None."""
    missing = [
        f"  • {field} — {desc}"
        for field, desc in _CRITICAL_FIELDS.items()
        if data.get(field) is None
    ]
    if missing:
        print(f"\n[ERROR] Missing critical fields for {label} ({data.get('ticker', '?')}):")
        print("\n".join(missing))
        print("\nPossible causes: invalid ticker, yfinance rate limit, or delisted security.")
        print("Tip: try again in a few seconds, or verify the ticker on finance.yahoo.com")
        sys.exit(1)


def main() -> None:
    print(BANNER)
    args = parse_args()

    acq = args.acquirer.upper()
    tgt = args.target.upper()

    # ── Step 1: Fetch ─────────────────────────────────────────────────────────
    print(f"[1/6] Fetching financials for {acq} and {tgt}...")
    try:
        acquirer_data, target_data = fetch_both(acq, tgt)
    except Exception as exc:
        print(f"\n[ERROR] Data fetch failed: {exc}")
        sys.exit(1)

    # Validate the target has enough data to run the model.
    # Acquirer data gaps are non-fatal — they only affect comparative metrics.
    _validate_or_exit(target_data, "target")

    # ── Step 2: Valuation multiples ───────────────────────────────────────────
    print("[2/6] Computing EV / EBITDA multiples...")
    acquirer_val = run_valuation(acquirer_data)
    target_val   = run_valuation(target_data)

    # ── Step 3: DCF (target only — we value what's being acquired) ───────────
    print("[3/6] Running DCF model on target...")
    target_dcf = run_dcf(target_data)

    # ── Step 4: Acquisition premium ───────────────────────────────────────────
    print("[4/6] Computing acquisition premium vs DCF implied price...")
    premium = compute_acquisition_premium(
        current_price=target_data.get("current_price"),
        implied_price=target_dcf.get("implied_share_price"),
    )

    # ── Step 5: Risk flags ────────────────────────────────────────────────────
    print("[5/6] Generating deal risk flags...")
    # Merge premium into the dcf dict so generate_risk_flags can access premium_pct
    dcf_with_premium = {**target_dcf, **premium}
    flags = generate_risk_flags(acquirer_data, target_data, target_val, dcf_with_premium)
    flags = apply_sector_flags(target_data, flags)

    # ── Step 6: Build PDF ─────────────────────────────────────────────────────
    print(f"[6/6] Building PDF report → {args.output}")
    try:
        build_report(
            acquirer_data=acquirer_data,
            target_data=target_data,
            acquirer_val=acquirer_val,
            target_val=target_val,
            target_dcf=target_dcf,
            premium=premium,
            flags=flags,
            output_path=args.output,
        )
    except Exception as exc:
        print(f"\n[ERROR] PDF generation failed: {exc}")
        raise

    print(f"\nPitchOS report saved to {args.output}")

    # Summary to terminal
    flag_count = len(flags)
    print(f"Risk flags : {flag_count}")
    if flag_count:
        for f in flags:
            print(f"  • {f}")


if __name__ == "__main__":
    main()
