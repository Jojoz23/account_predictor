#!/usr/bin/env python3
"""
Compare two credit-card Excel files and report repeated/duplicate transactions.
Use this to find why QuickBooks balance is off (e.g. duplicate imports).

Usage:
  python compare_credit_card_excels.py "all_transactions_categorized Scotia Visa.xlsx" "Book2.xlsx"
  python compare_credit_card_excels.py   # uses defaults in script
"""

import pandas as pd
import sys
from pathlib import Path
from collections import defaultdict

# Default files (relative to script folder or current dir)
DEFAULT_FILE_A = "all_transactions_categorized Scotia Visa.xlsx"
DEFAULT_FILE_B = "Book2.xlsx"


def normalize_key(row, date_col="Date", desc_col="Description", amt_col="Amount"):
    """Build a comparable key: (date_str, description_stripped, amount_rounded)."""
    try:
        dt = pd.to_datetime(row[date_col], errors="coerce")
        date_str = dt.strftime("%Y-%m-%d") if pd.notna(dt) else ""
    except Exception:
        date_str = str(row.get(date_col, ""))
    desc = str(row.get(desc_col, "")).strip()[:80]
    try:
        amt = round(float(row[amt_col]), 2) if pd.notna(row.get(amt_col)) else None
    except (TypeError, ValueError):
        amt = None
    return (date_str, desc, amt)


def load_transactions(path, label):
    """Load Excel and return (df, list of (key, index))."""
    path = Path(path)
    if not path.exists():
        # Try parent folder (Desktop)
        alt = path.parent.parent / path.name
        if alt.exists():
            path = alt
        else:
            print(f"ERROR: File not found: {path}")
            return None, []
    df = pd.read_excel(path, sheet_name=0)
    # Prefer standard names; some Excels use different column names
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    desc_col = "Description" if "Description" in df.columns else (df.columns[1] if len(df.columns) > 1 else None)
    amt_col = "Amount" if "Amount" in df.columns else None
    for c in df.columns:
        if c and "amount" in str(c).lower() and amt_col is None:
            amt_col = c
        if c and "desc" in str(c).lower() and desc_col is None:
            desc_col = c
    if desc_col is None or amt_col is None:
        print(f"  [{label}] Could not find Date/Description/Amount columns: {list(df.columns)}")
        return df, {}
    keys_to_indices = defaultdict(list)
    for idx, row in df.iterrows():
        if pd.isna(row.get(amt_col)) and "opening" in str(row.get(desc_col, "")).lower():
            continue
        k = normalize_key(row, date_col, desc_col, amt_col)
        if k[0] or k[1] or k[2] is not None:
            keys_to_indices[k].append((label, idx, row.get(date_col), row.get(desc_col), row.get(amt_col)))
    return df, keys_to_indices


def main():
    if len(sys.argv) >= 3:
        file_a, file_b = sys.argv[1], sys.argv[2]
    else:
        base = Path(__file__).resolve().parent
        file_a = base / DEFAULT_FILE_A
        file_b = base / DEFAULT_FILE_B
        if not file_b.exists():
            file_b = base.parent / DEFAULT_FILE_B

    print("Comparing credit card Excels for repeated/duplicate entries")
    print("=" * 60)
    print(f"  File A: {file_a}")
    print(f"  File B: {file_b}")
    print()

    df_a, keys_a = load_transactions(file_a, "A")
    if df_a is None:
        return 1
    df_b, keys_b = load_transactions(file_b, "B")
    if df_b is None:
        return 1

    # Build key -> list of (source, index, date, desc, amt)
    all_keys = defaultdict(list)
    for k, items in (keys_a if isinstance(keys_a, dict) else {}).items():
        for t in items:
            all_keys[k].append(t)
    for k, items in (keys_b if isinstance(keys_b, dict) else {}).items():
        for t in items:
            all_keys[k].append(t)

    # Duplicates within A
    dup_a = {k: v for k, v in all_keys.items() if sum(1 for t in v if t[0] == "A") > 1}
    # Duplicates within B
    dup_b = {k: v for k, v in all_keys.items() if sum(1 for t in v if t[0] == "B") > 1}
    # Key appears in both files (overlap)
    in_both = {k: v for k, v in all_keys.items() if any(t[0] == "A" for t in v) and any(t[0] == "B" for t in v)}
    # Repeated in either file (same key 2+ times in A or 2+ in B)
    repeated_in_a = {k: [t for t in v if t[0] == "A"] for k, v in all_keys.items() if sum(1 for t in v if t[0] == "A") > 1}
    repeated_in_b = {k: [t for t in v if t[0] == "B"] for k, v in all_keys.items() if sum(1 for t in v if t[0] == "B") > 1}

    print("SUMMARY")
    print("-" * 60)
    print(f"  Rows in A: {len(df_a)}  |  Rows in B: {len(df_b)}")
    print(f"  Unique keys in A: {len([k for k, v in all_keys.items() if any(t[0]=='A' for t in v)])}")
    print(f"  Unique keys in B: {len([k for k, v in all_keys.items() if any(t[0]=='B' for t in v)])}")
    print(f"  Keys in BOTH files: {len(in_both)}")
    print(f"  Keys repeated ONLY in A (duplicates within A): {len(repeated_in_a)}")
    print(f"  Keys repeated ONLY in B (duplicates within B): {len(repeated_in_b)}")
    print()

    # Count total duplicate rows
    extra_in_a = sum(len(v) - 1 for v in repeated_in_a.values())
    extra_in_b = sum(len(v) - 1 for v in repeated_in_b.values())
    if extra_in_a or extra_in_b:
        print("REPEATED ENTRIES (same Date + Description + Amount)")
        print("-" * 60)
        if repeated_in_a:
            print(f"  In File A: {extra_in_a} extra row(s) (same key repeated {sum(len(v) for v in repeated_in_a.values())} times total)")
            for i, (k, rows) in enumerate(list(repeated_in_a.items())[:15]):
                print(f"    e.g. {k[0]} | {k[1][:50]}... | {k[2]} -> {len(rows)} times")
            if len(repeated_in_a) > 15:
                print(f"    ... and {len(repeated_in_a) - 15} more repeated keys")
        if repeated_in_b:
            print(f"  In File B: {extra_in_b} extra row(s)")
            for i, (k, rows) in enumerate(list(repeated_in_b.items())[:15]):
                print(f"    e.g. {k[0]} | {k[1][:50]}... | {k[2]} -> {len(rows)} times")
            if len(repeated_in_b) > 15:
                print(f"    ... and {len(repeated_in_b) - 15} more repeated keys")
        print()

    # Optional: export duplicates to CSV for review
    out_csv = Path(file_a).parent / "compare_duplicates_report.csv"
    rows_out = []
    for k, items in all_keys.items():
        if len(items) > 1:
            for t in items:
                rows_out.append({
                    "source": t[0], "row_index": t[1], "date": t[2], "description": str(t[3])[:60], "amount": t[4],
                    "key_date": k[0], "key_desc": k[1][:60], "key_amount": k[2],
                    "times_this_key": len(items),
                })
    if rows_out:
        pd.DataFrame(rows_out).to_csv(out_csv, index=False)
        print(f"Report of all repeated keys (any file) written to: {out_csv}")
    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
