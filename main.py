"""
PitchOS entry point.

Parses CLI arguments for an M&A analysis run (acquirer ticker, target ticker, output PDF
filename), then orchestrates the full pipeline: data fetch → valuation → DCF → risk flags
→ PDF render. Currently echoes arguments; pipeline wiring added in later steps.
"""

import argparse


BANNER = """
╔══════════════════════════════════════╗
║           P I T C H  O S            ║
║    M&A Pitch Analysis Generator     ║
╚══════════════════════════════════════╝
"""


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


def main() -> None:
    print(BANNER)
    args = parse_args()
    print(f"Acquirer : {args.acquirer.upper()}")
    print(f"Target   : {args.target.upper()}")
    print(f"Output   : {args.output}")
    print()
    print("Pipeline not yet wired — arguments received successfully.")


if __name__ == "__main__":
    main()
