#!/usr/bin/env python3
"""
Diagnostic script to see what Camelot and the RBC chequing/savings extractor
see for a given RBC statement PDF.

This is read-only and DOES NOT affect the main pipeline.

Usage (from repo root):

  python explore_rbc_savings_camelot.py "data\\pdfs\\Andreani - Holding\\RBC Sav 8898\\3. Aug 2025.pdf"
"""

from pathlib import Path

import camelot
import pandas as pd

from test_rbc_chequing_complete import extract_rbc_chequing_statement


def show_camelot_tables(pdf_path: Path, flavor: str) -> None:
    print("=" * 80)
    print(f"CAMELOT TABLES ({flavor}, all pages): {pdf_path.name}")
    print("=" * 80)

    try:
        tables = camelot.read_pdf(str(pdf_path), pages="all", flavor=flavor)
    except Exception as e:
        print(f"  ❌ camelot.read_pdf failed: {e}")
        return

    print(f"  ✅ Camelot found {tables.n} table(s)\n")

    for idx, t in enumerate(tables, start=1):
        df = t.df
        print(f"  Table {idx}: page={t.page}, shape={df.shape}")
        max_rows = min(10, len(df))
        for r in range(max_rows):
            row_vals = [str(v) for v in df.iloc[r].tolist()]
            print(f"    Row {r}: {row_vals}")
        print()


def show_extractor_result(pdf_path: Path) -> None:
    print("=" * 80)
    print(f"RBC EXTRACTOR RESULT: {pdf_path.name}")
    print("=" * 80)

    df, opening, closing, year = extract_rbc_chequing_statement(str(pdf_path))

    if df is None or df.empty:
        print("  ❌ Extractor returned no transactions.")
        return

    print(f"  Extracted {len(df)} transactions")
    if opening is not None:
        print(f"  Opening balance: {opening:,.2f}")
    if closing is not None:
        print(f"  Closing balance: {closing:,.2f}")

    final_rb = None
    if "Running_Balance" in df.columns and df["Running_Balance"].notna().any():
        final_rb = float(df["Running_Balance"].iloc[-1])
        print(f"  Final running balance: {final_rb:,.2f}")
        if closing is not None:
            diff = abs(final_rb - closing)
            print(f"  Difference vs closing: {diff:,.2f}")

    print("\n  Last 5 rows of extracted DataFrame:")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df.tail(5).to_string(index=False))


def main(argv=None) -> None:
    import sys

    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python explore_rbc_savings_camelot.py <pdf_path>")
        sys.exit(1)

    pdf_path = Path(argv[0])
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    # Show both stream and lattice views to see what tables Camelot finds
    show_camelot_tables(pdf_path, flavor="stream")
    show_camelot_tables(pdf_path, flavor="lattice")
    show_extractor_result(pdf_path)


if __name__ == "__main__":
    main()

