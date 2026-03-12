#!/usr/bin/env python3
"""
Experimental extractor for TD Bank 0124 statements.

This is a copy of the original `extract_td_bank_statement` logic from
`test_td_bank_complete.py`, kept separate so we can safely tweak Camelot
settings for the 0124 account without affecting the main pipeline.

Usage (from repo root):

  python td_bank_0124_experiment.py "data/TD Bank - 0124/7. Dec 2025.pdf"
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import camelot
import pandas as pd
import pdfplumber

from test_td_bank_complete import extract_td_bank_statement


def extract_td_bank_statement_0124(pdf_path: str) -> Tuple[Optional[pd.DataFrame], Optional[float], Optional[float], Optional[int]]:
    """Extract transactions from TD Bank statement (0124 experiment).

    Strategy:
      1) First try the full original TD extractor (transaction tables on all pages).
         If it returns any transactions, use that result.
      2) If it finds no transactions (summary-only months), fall back to the
         Camelot lattice summary-table logic tailored for the 0124 account.
    """
    print(f"\n{'='*70}")
    print(f"EXPERIMENTAL TD 0124 EXTRACT: {Path(pdf_path).name}")
    print(f"{'='*70}\n")

    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    statement_start_year = None
    statement_end_year = None

    # 0) Try the original full TD extractor first
    print("0. TRYING ORIGINAL TD EXTRACTOR FIRST:")
    print("-" * 70)
    df_full, opening_full, closing_full, year_full = extract_td_bank_statement(pdf_path)
    if df_full is not None and not df_full.empty:
        print("  Original extractor returned transactions – using full detail result.\n")
        return df_full, opening_full, closing_full, year_full
    print("  Original extractor found no transactions, falling back to 0124 summary logic.\n")

    # Read full text once for period / account detection
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # 1) Extract statement period and years (unchanged from original)
    print("1. EXTRACTING STATEMENT PERIOD:")
    print("-" * 70)

    period_match = re.search(
        r"Statement From - To\s+([A-Z]{3}\s?\d{1,2}/\d{2})\s*-\s*([A-Z]{3}\s?\d{1,2}/\d{2})",
        full_text,
        re.IGNORECASE,
    )
    if not period_match:
        period_match = re.search(
            r"([A-Z]{3}\s?\d{1,2}/\d{2})\s*-\s*([A-Z]{3}\s?\d{1,2}/\d{2})",
            full_text,
            re.IGNORECASE,
        )

    if period_match:
        start_str = period_match.group(1).strip()
        end_str = period_match.group(2).strip()
        print(f"  Statement Period: {start_str} to {end_str}")

        start_year_match = re.search(r"/(\d{2})$", start_str)
        end_year_match = re.search(r"/(\d{2})$", end_str)

        if start_year_match and end_year_match:
            start_year_short = int(start_year_match.group(1))
            end_year_short = int(end_year_match.group(1))

            statement_start_year = 2000 + start_year_short
            statement_end_year = 2000 + end_year_short
            statement_year = statement_end_year

            print(f"  Statement Start Year: {statement_start_year}")
            print(f"  Statement End Year: {statement_end_year}")
            print(f"  Primary Statement Year: {statement_year}")
    else:
        print("  WARNING: Could not extract statement period")
        statement_year = 2025
        statement_start_year = 2024
        statement_end_year = 2025
        print(f"  Using fallback year: {statement_year}")

    # 2) Extract transactions using Camelot lattice on page 1
    print("\n2. EXTRACTING TRANSACTIONS WITH CAMELOT (lattice experiment):")
    print("-" * 70)

    try:
        tables = camelot.read_pdf(
            pdf_path,
            pages="1",
            flavor="lattice",
            strip_text="\n",
        )
    except Exception as e:
        print(f"  ERROR: Camelot lattice failed: {e}")
        tables = []

    chosen_table = None
    chosen_header_row = None

    for t_idx, table in enumerate(tables, start=1):
        df = table.df
        if df.shape[0] < 2 or df.shape[1] < 5:
            continue

        # Look for header row with DESCRIPTION / DEBIT / DEPOSIT / DATE / BALANCE
        header_row = None
        for i in range(len(df)):
            row_text = " ".join(df.iloc[i].astype(str).tolist()).upper()
            if (
                "DESCRIPTION" in row_text
                and ("DEBIT" in row_text or "CHEQUE" in row_text)
                and ("DEPOSIT" in row_text or "CREDIT" in row_text)
                and "DATE" in row_text
                and "BALANCE" in row_text
            ):
                header_row = i
                break

        if header_row is not None:
            chosen_table = df
            chosen_header_row = header_row
            print(f"  Using table {t_idx} as transaction summary (rows={df.shape[0]}, cols={df.shape[1]})")
            break

    if chosen_table is None:
        print("  WARNING: No suitable header row found in lattice tables.")
    else:
        # Parse summary-style rows (like the MONTHLY PLAN FEE example)
        # Mirror main TD extractor column roles:
        #   DESCRIPTION / CHEQUE/DEBIT / DEPOSIT/CREDIT / DATE / BALANCE
        desc_col = 0
        debit_col = 1
        credit_col = 2
        date_col = 3
        balance_col = 4

        for row_idx in range(chosen_header_row + 1, len(chosen_table)):
            row = chosen_table.iloc[row_idx].tolist()
            desc = str(row[desc_col]) if desc_col < len(row) else ""
            if not desc.strip():
                continue

            desc_upper = desc.upper()

            # Opening balance if embedded in "BALANCE FORWARD..."
            if "BALANCE FORWARD" in desc_upper:
                bal_text = str(row[balance_col]) if balance_col < len(row) else ""
                bal_text = bal_text.replace(",", "").replace("$", "")
                parts = re.findall(r"-?\d+\.\d{2}", bal_text)
                if parts:
                    try:
                        opening_balance = float(parts[0])
                        closing_balance = float(parts[-1])
                        print(f"  Opening Balance (summary table): ${opening_balance:,.2f}")
                        print(f"  Closing Balance (summary table): ${closing_balance:,.2f}")
                    except Exception:
                        pass
                # If this same row also contains the monthly fee, don't skip it:
                # let it fall through so we can create a fee transaction below.
                if "MONTHLY PLAN FEE" not in desc_upper:
                    continue

            # Skip non-transaction summary rows
            if any(
                kw in desc_upper
                for kw in ["NEXT STATEMENT", "DEP CONTENT", "ITEMS", "UNC BATCH", "CREDITS", "DEBITS"]
            ):
                continue

            # Extract withdrawal (debit) and deposit (credit) amounts, mirroring main extractor
            withdrawal = None
            deposit = None

            if debit_col < len(row) and row[debit_col]:
                try:
                    withdrawal = float(str(row[debit_col]).replace(",", "").replace("$", ""))
                except Exception:
                    withdrawal = None

            if credit_col < len(row) and row[credit_col]:
                try:
                    deposit = float(str(row[credit_col]).replace(",", "").replace("$", ""))
                except Exception:
                    deposit = None

            # Skip if no amounts (mirror main extractor's behavior)
            if withdrawal is None and deposit is None:
                continue

            # Extract date from date column (e.g. "NOV28DEC31")
            raw_date = str(row[date_col]) if date_col < len(row) else ""
            raw_date_clean = raw_date.replace(" ", "").upper()
            # Take the last 3-letter month+day if two are concatenated
            m = re.findall(r"[A-Z]{3}\d{1,2}", raw_date_clean)
            fee_date_str = None
            if m:
                month_day = m[-1]
                mm = re.match(r"([A-Z]{3})(\d{1,2})", month_day)
                if mm and statement_end_year:
                    mon = mm.group(1)
                    day = int(mm.group(2))
                    mon_num = {
                        "JAN": 1,
                        "FEB": 2,
                        "MAR": 3,
                        "APR": 4,
                        "MAY": 5,
                        "JUN": 6,
                        "JUL": 7,
                        "AUG": 8,
                        "SEP": 9,
                        "OCT": 10,
                        "NOV": 11,
                        "DEC": 12,
                    }.get(mon)
                    if mon_num:
                        try:
                            fee_date = datetime(statement_end_year, mon_num, day)
                            fee_date_str = fee_date.strftime("%Y-%m-%d")
                        except Exception:
                            fee_date_str = month_day
                if fee_date_str is None:
                    fee_date_str = month_day
            else:
                fee_date_str = raw_date

            transactions.append(
                {
                    "Date": fee_date_str,
                    "Description": desc,
                    "Withdrawals": withdrawal if withdrawal is not None else 0.0,
                    "Deposits": deposit if deposit is not None else 0.0,
                    "Balance": None,
                }
            )

    # Build DataFrame
    df = pd.DataFrame(transactions)

    if df.empty:
        print("  WARNING: No transactions extracted in experimental 0124 path.")
        return None, opening_balance, closing_balance, statement_year

    print(f"\n  Extracted {len(df)} transaction(s) in experimental 0124 path")

    # Simple running balance if we have opening balance and balances are missing
    if opening_balance is not None:
        print("\n3. CALCULATING RUNNING BALANCE (experimental):")
        print("-" * 70)
        df["Net_Change"] = df["Deposits"].fillna(0) - df["Withdrawals"].fillna(0)
        df["Running_Balance"] = opening_balance + df["Net_Change"].cumsum()
        if closing_balance is not None:
            final_rb = df["Running_Balance"].iloc[-1]
            diff = abs(final_rb - closing_balance)
            print(f"  Opening Balance: ${opening_balance:,.2f}")
            print(f"  Closing Balance: ${closing_balance:,.2f}")
            print(f"  Final Running Balance: ${final_rb:,.2f}")
            print(f"  Difference: ${diff:,.2f}")

    return df, opening_balance, closing_balance, statement_year


def main(argv=None) -> None:
    import sys

    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python td_bank_0124_experiment.py <pdf_path>")
        sys.exit(1)

    pdf_path = argv[0]
    df, opening, closing, year = extract_td_bank_statement_0124(pdf_path)
    if df is not None:
        print("\nPreview of extracted DataFrame:")
        print(df.head())


if __name__ == "__main__":
    main()

