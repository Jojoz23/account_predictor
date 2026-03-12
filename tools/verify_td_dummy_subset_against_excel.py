#!/usr/bin/env python3
"""
Verify that all TRNS rows in the TD 5931 dummy H+GST subset IIF
exist in the source Excel (TD Bank - 5931.xlsx) with the same
date, bank amount, and memo (description).

Logic:
  - Read Excel, compute a signed Amount per row:
      * If 'Amount' column exists: use it.
      * Else, if 'Debit'/'Credit' exist:
            amount = Credit - Debit
        (so deposits positive, withdrawals negative).
  - Normalise Excel dates to MM/DD/YYYY strings (to match IIF).
  - Rebuild the IIF memo exactly like excel_to_iif does:
        memo = Description [+ ' ' + extra_desc] truncated to 100 chars,
        where extra_desc is typically the unnamed column before Account.
  - Build a multiset of (date_str, amount, memo) from Excel.
  - Parse the dummy subset IIF and, for each TRNS line:
        key = (DATE, AMOUNT, MEMO)
        consume one instance from the Excel multiset.
  - Report:
      * how many TRNS rows matched a row in Excel
      * TRNS rows that could NOT be found in Excel
      * Excel rows that were never consumed (not used in IIF subset)
"""

from collections import Counter
from pathlib import Path
from typing import Tuple, Counter as CounterType

import pandas as pd


EXCEL_PATH = Path(r"data/iif/114 - lovely/TD Bank - 5931.xlsx")
IIF_PATH = Path(r"data/iif/114 - lovely/TD Bank - 5931_dummy_H_and_GST_subset.iif")


def load_excel_keys() -> CounterType[Tuple[str, float, str]]:
    df = pd.read_excel(EXCEL_PATH, sheet_name=0)
    cols = {c.lower(): c for c in df.columns}

    # Compute signed amount
    if "amount" in cols:
        amt = pd.to_numeric(df[cols["amount"]], errors="coerce")
    else:
        # Try Debit + Credit or Debit + Deposit pattern
        has_debit = "debit" in cols
        has_credit = "credit" in cols
        has_deposit = "deposit" in cols

        if has_debit and (has_credit or has_deposit):
            debit = pd.to_numeric(df[cols["debit"]], errors="coerce").fillna(0.0)
            if has_credit:
                credit_like = pd.to_numeric(
                    df[cols["credit"]], errors="coerce"
                ).fillna(0.0)
            else:
                credit_like = pd.to_numeric(
                    df[cols["deposit"]], errors="coerce"
                ).fillna(0.0)
            # Same convention as excel_to_iif: deposits positive, withdrawals negative
            amt = credit_like - debit
        else:
            raise RuntimeError(
                f"Could not find Amount or Debit/Credit/Deposit columns in Excel: {df.columns}"
            )

    # Date normalisation
    if "date" not in cols:
        raise RuntimeError("Could not find 'Date' column in Excel.")

    date_series = pd.to_datetime(df[cols["date"]], errors="coerce")
    date_str = date_series.dt.strftime("%m/%d/%Y")

    # Rebuild memo the same way excel_to_iif.py does
    desc_col = cols.get("description")
    account_col = cols.get("account")

    # Detect extra description column (unnamed before Account)
    extra_desc_col = None
    if account_col is not None:
        col_list = list(df.columns)
        acc_idx = col_list.index(account_col)
        if acc_idx > 0:
            prev_col = col_list[acc_idx - 1]
            # Typical pattern: 'Unnamed: 2'
            if isinstance(prev_col, str) and prev_col.startswith("Unnamed"):
                # Use it only if it has some data
                if df[prev_col].notna().sum() > 0:
                    extra_desc_col = prev_col

    keys: CounterType[Tuple[str, float, str]] = Counter()
    for idx, (d, a) in enumerate(zip(date_str, amt)):
        if pd.isna(d) or pd.isna(a):
            continue

        # Base description
        if desc_col is not None:
            base_desc_val = df.at[idx, desc_col]
            base_desc = "" if pd.isna(base_desc_val) else str(base_desc_val)
        else:
            base_desc = ""

        memo = base_desc.strip()

        # Optional extra description
        if extra_desc_col is not None:
            extra_val = df.at[idx, extra_desc_col]
            if extra_val is not None and not pd.isna(extra_val):
                extra_text = str(extra_val).strip()
                if extra_text:
                    if memo:
                        memo = f"{memo} {extra_text}"
                    else:
                        memo = extra_text

        memo = memo[:100]  # IIF truncation

        k = (str(d), round(float(a), 2), memo)
        keys[k] += 1

    return keys


def load_iif_trns_keys() -> CounterType[Tuple[str, float, str]]:
    lines = IIF_PATH.read_text(encoding="utf-8").splitlines()
    keys: CounterType[Tuple[str, float, str]] = Counter()

    for line in lines:
        if not line.startswith("TRNS\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        date_str = parts[3]
        memo = parts[9] if len(parts) > 9 else ""
        try:
            amt = float(parts[7])
        except Exception:
            continue
        k = (date_str, round(amt, 2), memo[:100])
        keys[k] += 1

    return keys


def main() -> None:
    print(f"Excel: {EXCEL_PATH}")
    print(f"IIF  : {IIF_PATH}")
    print()

    excel_keys = load_excel_keys()
    iif_keys = load_iif_trns_keys()

    total_iif = sum(iif_keys.values())
    total_excel = sum(excel_keys.values())
    print(f"Excel rows with usable Date+Amount : {total_excel}")
    print(f"IIF TRNS rows in dummy subset      : {total_iif}")
    print()

    # Check which IIF TRNS are missing in Excel
    missing_from_excel = []
    excel_leftovers = excel_keys.copy()

    for key, cnt in iif_keys.items():
        available = excel_leftovers.get(key, 0)
        if available >= cnt:
            excel_leftovers[key] = available - cnt
            if excel_leftovers[key] == 0:
                del excel_leftovers[key]
        else:
            # Some or all of these TRNS can't be matched
            missing_from_excel.append((key, cnt - available))
            if key in excel_leftovers:
                del excel_leftovers[key]

    if not missing_from_excel:
        print("All IIF TRNS (date, amount) pairs are present in the Excel.")
    else:
        print("❌ Some IIF TRNS rows could not be matched to Excel:")
        for (d, a), diff in missing_from_excel:
            print(f"  {diff}x missing: Date={d}, Amount={a:.2f}")

    if excel_leftovers:
        print()
        print("Excel rows that did not appear in the dummy subset IIF (first 20):")
        shown = 0
        for (d, a, memo), cnt in excel_leftovers.items():
            print(f"  {cnt}x Excel-only: Date={d}, Amount={a:.2f}, Memo={memo!r}")
            shown += 1
            if shown >= 20:
                break
    else:
        print()
        print("No Excel-only rows; every Excel Date+Amount was used by the dummy subset.")


if __name__ == "__main__":
    main()

