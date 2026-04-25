#!/usr/bin/env python3
"""
Write per-statement detailed extracts for RBC review.
Creates one CSV per PDF with Date/Description/Withdrawals/Deposits/Balance/Running_Balance.
"""

from pathlib import Path
import pandas as pd

from test_rbc_chequing_complete import extract_rbc_chequing_statement


def main(folder="data/rbc"):
    pdfs = sorted(Path(folder).glob("*.pdf"))
    out_dir = Path(folder) / "debug_rbc_mismatch_details"
    out_dir.mkdir(exist_ok=True)

    for pdf in pdfs:
        df, opening, closing, year = extract_rbc_chequing_statement(str(pdf))
        if df is None:
            continue
        detail = df.copy()
        detail["_opening_balance"] = opening
        detail["_closing_balance"] = closing
        detail["_statement_year"] = year
        out_csv = out_dir / f"{pdf.stem}_details.csv"
        detail.to_csv(out_csv, index=False)
        print(f"Saved: {out_csv}")


if __name__ == "__main__":
    main()
