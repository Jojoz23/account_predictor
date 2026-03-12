#!/usr/bin/env python3
"""
Small helper script to investigate which Camelot settings work
for TD Bank 0124 PDFs (or any other PDF you pass in).

Usage (from repo root):

  python explore_td_bank_camelot.py "data/TD Bank - 0124/7. Dec 2025.pdf"

It will:
  - Run Camelot with multiple configurations (flavor / line_scale / edge_tol)
  - Print table shapes and the first few rows for each table on each page

This script is for manual investigation only and is NOT used by the main pipeline.
"""

import sys
from pathlib import Path

import camelot


CONFIGS = [
    # (name, kwargs)
    ("stream_default", {"flavor": "stream"}),
    ("stream_tight", {"flavor": "stream", "edge_tol": 50}),
    ("stream_loose", {"flavor": "stream", "edge_tol": 200}),
    ("lattice_default", {"flavor": "lattice"}),
    ("lattice_scale_40", {"flavor": "lattice", "line_scale": 40}),
    ("lattice_scale_60", {"flavor": "lattice", "line_scale": 60}),
]


def explore_pdf(pdf_path: str) -> None:
    path = Path(pdf_path)
    if not path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return

    print("=" * 80)
    print(f"EXPLORING PDF WITH CAMELOT: {path.name}")
    print("=" * 80)

    for cfg_name, cfg in CONFIGS:
        print("\n" + "-" * 80)
        print(f"CONFIG: {cfg_name}  ({cfg})")
        print("-" * 80)

        try:
            tables = camelot.read_pdf(
                str(path),
                pages="all",
                strip_text="\n",
                **cfg,
            )
        except Exception as e:
            print(f"  ❌ Camelot failed for config {cfg_name}: {e}")
            continue

        print(f"  ✅ Found {tables.n} table(s)")

        for idx, table in enumerate(tables, start=1):
            df = table.df
            print(f"\n  Table {idx}: shape={df.shape}, page={table.page}")
            # Print header and first few rows
            max_rows = min(8, len(df))
            if max_rows == 0:
                print("    (empty table)")
                continue

            for i in range(max_rows):
                row_vals = [str(v) for v in df.iloc[i].tolist()]
                print(f"    Row {i}: {row_vals}")


def main(argv=None) -> None:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python explore_td_bank_camelot.py <pdf_path>")
        sys.exit(1)

    explore_pdf(argv[0])


if __name__ == "__main__":
    main()

