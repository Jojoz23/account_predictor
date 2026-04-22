#!/usr/bin/env python3
"""
Probe TD Camelot extraction and reconcile against statement balances.

Usage:
  .venv311\\Scripts\\python.exe tools\\td_camelot_probe.py "path\\to\\td_statement.pdf"
"""

from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_td_bank_complete import extract_td_bank_statement_camelot


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/td_camelot_probe.py <td_pdf_path>")
        return 1

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return 1

    df, opening, closing, year = extract_td_bank_statement_camelot(str(pdf_path))
    if df is None or df.empty:
        print("No transactions extracted.")
        return 2

    w = pd.to_numeric(df.get("Withdrawals"), errors="coerce").fillna(0).sum()
    d = pd.to_numeric(df.get("Deposits"), errors="coerce").fillna(0).sum()
    calc_close = (opening or 0.0) + d - w

    print("\n=== TD Camelot Probe ===")
    print(f"PDF: {pdf_path.name}")
    print(f"Rows: {len(df)}")
    print(f"Statement year: {year}")
    print(f"Opening: {opening}")
    print(f"Closing: {closing}")
    print(f"Sum Withdrawals: {w:.2f}")
    print(f"Sum Deposits:   {d:.2f}")
    print(f"Calc close:     {calc_close:.2f}")
    if closing is not None:
        print(f"Difference:     {abs(calc_close - float(closing)):.2f}")

    print("\nTop deposits:")
    print(
        df.sort_values("Deposits", ascending=False)[
            ["Date", "Description", "Withdrawals", "Deposits", "Balance"]
        ]
        .head(12)
        .to_string(index=False)
    )

    print("\nTop withdrawals:")
    print(
        df.sort_values("Withdrawals", ascending=False)[
            ["Date", "Description", "Withdrawals", "Deposits", "Balance"]
        ]
        .head(12)
        .to_string(index=False)
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

