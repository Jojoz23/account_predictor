#!/usr/bin/env python3
"""
Dump raw Camelot table outputs for RBC PDFs.
Creates CSV files for every detected table to inspect exact extracted cells.
"""

from pathlib import Path
import camelot
import pandas as pd


def main(folder="data/rbc"):
    pdfs = sorted(Path(folder).glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {folder}")
        return

    out_root = Path(folder) / "debug_rbc_camelot_raw"
    out_root.mkdir(exist_ok=True)

    summary_rows = []

    for pdf in pdfs:
        print(f"\n=== {pdf.name} ===")
        pdf_out = out_root / pdf.stem
        pdf_out.mkdir(exist_ok=True)

        try:
            tables = camelot.read_pdf(str(pdf), pages="all", flavor="stream")
        except Exception as exc:
            print(f"Camelot failed: {exc}")
            summary_rows.append({"file": pdf.name, "table_count": 0, "error": str(exc)})
            continue

        print(f"tables found: {len(tables)}")
        summary_rows.append({"file": pdf.name, "table_count": len(tables), "error": ""})

        for i, table in enumerate(tables, start=1):
            df = table.df.copy()
            raw_csv = pdf_out / f"table_{i:02d}.csv"
            df.to_csv(raw_csv, index=False, header=False)

            # Also save a normalized version to make reading easier.
            norm = df.applymap(lambda x: str(x).replace("\n", " ").strip())
            norm_csv = pdf_out / f"table_{i:02d}_normalized.csv"
            norm.to_csv(norm_csv, index=False, header=False)

    summary_path = out_root / "camelot_tables_summary.xlsx"
    pd.DataFrame(summary_rows).to_excel(summary_path, index=False)
    print(f"\nSaved summary: {summary_path}")


if __name__ == "__main__":
    main()
