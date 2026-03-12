#!/usr/bin/env python3
"""
Quick helper to inspect Excel statement files for obvious "gaps":
- missing Date / Description / Amount / Account

Usage (from repo root):

  python tools/check_excel_gaps.py "data\\iif\\114 - lovely"

It prints a summary per .xlsx file and flags files that look clean.
"""

from pathlib import Path

import pandas as pd


def check_folder(folder_path: str) -> None:
    folder = Path(folder_path)
    if not folder.exists():
        print(f"❌ Folder not found: {folder_path}")
        return

    excel_files = sorted(folder.glob("*.xlsx"))
    if not excel_files:
        print(f"❌ No .xlsx files found in {folder}")
        return

    print(f"Checking {len(excel_files)} Excel file(s) in {folder}...\n")

    for excel_path in excel_files:
        print("=" * 80)
        print(excel_path.name)
        try:
            df = pd.read_excel(excel_path, sheet_name=0)
        except Exception as e:
            print(f"  ERROR reading Excel: {e}")
            continue

        print(f"  Rows: {len(df)}")
        print(f"  Columns: {list(df.columns)}")

        has_gaps = False

        for col in ["Date", "Description", "Amount", "Account"]:
            if col in df.columns:
                missing = df[col].isna() | (df[col].astype(str).str.strip() == "")
                count_missing = int(missing.sum())
                print(f"  Missing/blank {col}: {count_missing}")
                if count_missing > 0 and col in {"Amount", "Account"}:
                    has_gaps = True

        # More precise check: rows with a real description but missing Account
        if "Account" in df.columns and "Description" in df.columns:
            desc_ok = ~(df["Description"].isna() | (df["Description"].astype(str).str.strip() == ""))
            acc_missing = df["Account"].isna() | (df["Account"].astype(str).str.strip() == "")
            uncategorized = int((desc_ok & acc_missing).sum())
            print(f"  Rows with description but NO Account (uncategorized): {uncategorized}")
            if uncategorized > 0:
                has_gaps = True

        print(f"  CLEAN_STATUS: {'NO_GAPS' if not has_gaps else 'HAS_GAPS'}")
        print()


def main(argv=None) -> None:
    import sys

    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python tools/check_excel_gaps.py <folder_with_excels>")
        sys.exit(1)

    check_folder(argv[0])


if __name__ == "__main__":
    main()

