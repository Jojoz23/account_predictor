#!/usr/bin/env python3
"""
Explore RBC statement balance mismatches at file level.
Generates an Excel report with extracted-vs-expected balance deltas.
"""

from pathlib import Path
import pandas as pd

from test_rbc_chequing_complete import extract_rbc_chequing_statement


def main(folder="data/rbc"):
    pdfs = sorted(Path(folder).glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {folder}")
        return

    rows = []
    for pdf in pdfs:
        df, opening, closing, year = extract_rbc_chequing_statement(str(pdf))
        extracted_ok = df is not None and not df.empty
        final_rb = None
        diff = None
        adjustment_rows = 0

        if extracted_ok and "Running_Balance" in df.columns and not df["Running_Balance"].isna().all():
            final_rb = float(df["Running_Balance"].dropna().iloc[-1])
        if closing is not None and final_rb is not None:
            diff = final_rb - float(closing)
        if extracted_ok and "Description" in df.columns:
            adjustment_rows = int(
                df["Description"].astype(str).str.contains("Balance reconciliation adjustment", case=False, na=False).sum()
            )

        rows.append(
            {
                "file": pdf.name,
                "year": year,
                "rows": 0 if df is None else len(df),
                "opening_balance": opening,
                "closing_balance": closing,
                "final_running_balance": final_rb,
                "balance_diff": diff,
                "balance_match": (abs(diff) < 0.01) if diff is not None else False,
                "adjustment_rows": adjustment_rows,
                "extracted_ok": extracted_ok,
            }
        )

    out = pd.DataFrame(rows)
    out_path = Path(folder) / "rbc_balance_mismatch_report.xlsx"
    out.to_excel(out_path, index=False)
    print(f"Saved: {out_path}")
    print(out[["file", "rows", "closing_balance", "final_running_balance", "balance_diff", "balance_match", "adjustment_rows"]].to_string(index=False))


if __name__ == "__main__":
    main()
