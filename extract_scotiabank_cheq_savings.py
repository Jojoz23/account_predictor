#!/usr/bin/env python3
"""
Standalone extractor for Scotiabank chequing/savings statements that use:
  "Date | Transactions | withdrawn ($) | deposited ($) | Balance ($)"
(e.g. Scotiabank Cheq 0725, personal savings style).
Returns: df (Date, Description, Withdrawals, Deposits, Running_Balance), opening_balance, closing_balance, statement_year.
"""
import re
import pandas as pd
from pathlib import Path
from datetime import datetime

import camelot

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}


def _parse_amount(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s).strip().replace('$', '').replace(',', '')
    if not s or s == '-' or s == '—':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date_cell(date_str, statement_year):
    """Parse 'Dec 24', 'Jan 2' style; use statement_year for year."""
    if not date_str or pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    m = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\.?\s*(\d{1,2})', date_str, re.I)
    if not m:
        return None
    month = MONTHS.get(m.group(1).lower())
    day = int(m.group(2))
    if month is None:
        return None
    try:
        return datetime(int(statement_year), month, day)
    except (ValueError, TypeError):
        return None


def _parse_date_mdy(date_str):
    """Parse MM/DD/YYYY or M/D/YYYY (e.g. 01/03/2025, 12/31/2024) - Scotia Business style."""
    if not date_str or pd.isna(date_str):
        return None
    # Normalize: Camelot sometimes splits "12/31/2024" as "1\\n2/31/2024"
    date_str = str(date_str).strip().replace('\n', '').replace('\r', '').replace(' ', '')
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if not m:
        return None
    try:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(year, month, day)
    except (ValueError, TypeError):
        return None


def extract_scotiabank_cheq_savings(pdf_path: str):
    """
    Extract from Scotiabank PDFs with header:
      Date | Transactions | withdrawn ($) | deposited ($) | Balance ($)
    """
    pdf_path = Path(pdf_path)
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None

    tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")

    # Process ALL tables with this header so we get BALANCE FORWARD from any table and merge transactions
    for ti, t in enumerate(tables):
        df = t.df.fillna('')
        for idx in range(min(15, len(df))):
            row = df.iloc[idx]
            row_text = ' '.join([str(c) for c in row.tolist()]).lower().replace('\xa0', ' ').replace('\n', ' ').replace('\r', ' ')
            if 'balance' not in row_text or '($)' not in row_text:
                continue
            if not ('date' in row_text or 'd ate' in row_text):
                continue
            if not ('transactions' in row_text or 'description' in row_text):
                continue
            if not ('withdrawn' in row_text or 'withdrawal' in row_text or 'debit' in row_text):
                continue
            if not ('deposited' in row_text or 'deposit' in row_text or 'credit' in row_text):
                continue

            headers = [str(c).replace('\n', ' ').strip().lower() for c in row.tolist()]
            date_idx = desc_idx = wdr_idx = dep_idx = bal_idx = None
            for i, h in enumerate(headers):
                if ('date' in h or 'd ate' in h) and date_idx is None:
                    date_idx = i
                elif 'transaction' in h or 'description' in h:
                    desc_idx = i
                elif 'withdrawn' in h or 'withdrawal' in h or 'debit' in h:
                    wdr_idx = i
                elif 'deposited' in h or 'deposit' in h or 'credit' in h:
                    dep_idx = i
                elif 'balance' in h:
                    bal_idx = i
            if date_idx is None or desc_idx is None or bal_idx is None:
                continue

            for r in range(idx + 1, min(idx + 20, len(df))):
                rrow = df.iloc[r]
                cells = [str(rrow.iloc[j]).strip() if j < len(rrow) else '' for j in range(max(len(headers), bal_idx + 1))]
                dt_cell = cells[date_idx] if date_idx < len(cells) else ''
                if not dt_cell:
                    continue
                parsed_mdy = _parse_date_mdy(dt_cell)
                if parsed_mdy is not None:
                    statement_year = parsed_mdy.year
                    break
                yr_m = re.search(r'20\d{2}', ' '.join(cells))
                if yr_m:
                    statement_year = int(yr_m.group(0))
                    break
                mon_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\.?\s*(\d{1,2})', dt_cell, re.I)
                if mon_match:
                    statement_year = 2025
                    break
            if statement_year is None:
                statement_year = 2025

            ncols = max(date_idx, desc_idx, bal_idx) + 3
            for r in range(idx + 1, len(df)):
                rrow = df.iloc[r]
                cells = [str(rrow.iloc[j]).strip().replace('\n', ' ') if j < len(rrow) else '' for j in range(ncols)]
                dt_cell = cells[date_idx] if date_idx < len(cells) else ''
                desc_cell = cells[desc_idx] if desc_idx < len(cells) else ''
                wdr_val = _parse_amount(cells[wdr_idx]) if wdr_idx is not None and wdr_idx < len(cells) else None
                dep_val = _parse_amount(cells[dep_idx]) if dep_idx is not None and dep_idx < len(cells) else None
                bal_val = _parse_amount(cells[bal_idx]) if bal_idx is not None and bal_idx < len(cells) else None
                if wdr_val is None and dep_val is None and bal_val is not None and len(cells) > 4:
                    for c in range(date_idx + 1, min(len(cells), bal_idx or len(cells))):
                        if c in (date_idx, desc_idx):
                            continue
                        amt = _parse_amount(cells[c])
                        if amt is not None:
                            if wdr_val is None and (dep_idx is None or c < dep_idx):
                                wdr_val = amt
                            elif dep_val is None:
                                dep_val = amt
                            break
                desc_upper = desc_cell.upper().replace('\n', ' ').replace('\r', ' ').replace('\xa0', ' ')
                _is_opening = (
                    'OPENING BALANCE' in desc_upper
                    or 'BALANCE FORWARD' in desc_upper
                    or ('BALANCE' in desc_upper and 'FORWARD' in desc_upper)
                )
                _is_closing_summary = 'CLOSING BALANCE' in desc_upper and wdr_val is None and dep_val is None
                if _is_closing_summary:
                    continue  # skip summary row; closing_balance already set from last real transaction
                if _is_opening:
                    if bal_val is not None and opening_balance is None:
                        opening_balance = bal_val
                    continue
                if not dt_cell and not desc_cell and wdr_val is None and dep_val is None:
                    continue

                date_parsed = _parse_date_mdy(dt_cell) or _parse_date_cell(dt_cell, statement_year)
                if date_parsed and desc_cell:
                    transactions.append({
                        'Date': date_parsed,
                        'Description': desc_cell.strip(),
                        'Withdrawals': wdr_val if wdr_val is not None else 0.0,
                        'Deposits': dep_val if dep_val is not None else 0.0,
                        'Balance': bal_val,
                    })
                    if bal_val is not None:
                        closing_balance = bal_val
                elif desc_cell.strip() and transactions and wdr_val is None and dep_val is None and bal_val is None:
                    # Continuation row: multiline description (no date, no amounts); merge into previous transaction
                    transactions[-1]['Description'] = (transactions[-1]['Description'] + ' ' + desc_cell.strip()).strip()

    if not transactions:
        return pd.DataFrame(), opening_balance, closing_balance, statement_year or 2025

    out = pd.DataFrame(transactions)
    # Include Balance in dedupe so same-day same-amount transactions (e.g. two 2000 transfers) are both kept
    out = out.drop_duplicates(
        subset=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'],
        keep='first'
    )
    out = out.sort_values('Date').reset_index(drop=True)
    opening = opening_balance if opening_balance is not None else 0.0
    out['Running_Balance'] = opening + (out['Deposits'] - out['Withdrawals']).cumsum()
    # Use chronologically last row's balance as closing (true statement ending balance)
    if out['Balance'].notna().any():
        closing_balance = float(out['Balance'].dropna().iloc[-1])
    return out, opening_balance, closing_balance, statement_year or 2025


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/Scotiabank Cheq 0725/1. January 2025.pdf"
    df, open_b, close_b, year = extract_scotiabank_cheq_savings(path)
    print(f"Opening: {open_b}, Closing: {close_b}, Year: {year}")
    print(f"Transactions: {len(df)}")
    if len(df) > 0:
        print(df.head(10).to_string())
        print("...")
        print(df.tail(5).to_string())
        if close_b is not None and len(df) > 0:
            last_rb = df['Running_Balance'].iloc[-1]
            print(f"\nLast Running_Balance: {last_rb:.2f}, Closing: {close_b}, Match: {abs(last_rb - close_b) < 0.02}")
