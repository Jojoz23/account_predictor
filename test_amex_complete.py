#!/usr/bin/env python3
"""
AMEX Credit Card statement extraction - Camelot only.
Extracts transactions, opening/closing balance from Amex Bank of Canada (Platinum Card) PDFs.
"""
import re
import pandas as pd
from pathlib import Path
from datetime import datetime
import camelot

# Month abbreviation to number
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


def _parse_date(date_str, statement_year, closing_month=1):
    """
    Parse 'Jan 8' or 'Dec 26' style. Use statement_year; if month is Dec and
    closing_month is Jan, use statement_year - 1 for December.
    """
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
    year = int(statement_year)
    if month == 12 and closing_month == 1:
        year = statement_year - 1
    try:
        return datetime(year, month, day)
    except (ValueError, TypeError):
        return None


def extract_amex_statement(pdf_path: str):
    """
    Extract Amex Bank of Canada Platinum Card statement using Camelot only.

    Returns:
        df: DataFrame with Date, Description, Amount, Running_Balance
        opening_balance: float or None
        closing_balance: float or None
        statement_year: int (from closing date)
    """
    pdf_path = Path(pdf_path)
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    closing_month = 1  # default Jan

    # Camelot: read all pages with stream
    tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")

    # 1) Find opening/closing and statement year from first tables (Table 2 = index 1)
    for ti, t in enumerate(tables):
        df = t.df.fillna('')
        full_text = ' '.join(df.values.astype(str).flatten().tolist()).upper()
        # Previous Balance
        if opening_balance is None and 'PREVIOUS BALANCE' in full_text:
            for _, row in df.iterrows():
                row_str = ' '.join([str(x) for x in row.tolist()])
                if 'PREVIOUS BALANCE' in row_str.upper():
                    amt = re.search(r'[-]?\$?([\d,]+\.\d{2})', row_str)
                    if amt:
                        try:
                            opening_balance = float(amt.group(1).replace(',', ''))
                            # PDF shows -233.82 for credit (previous balance negative = credit)
                            if '-' in row_str and 'PREVIOUS' in row_str.upper():
                                opening_balance = -opening_balance
                            break
                        except ValueError:
                            pass
        # New Balance
        if closing_balance is None and ('NEW BALANCE' in full_text or 'EQUALS NEW BALANCE' in full_text):
            for _, row in df.iterrows():
                row_str = ' '.join([str(x) for x in row.tolist()])
                if 'NEW BALANCE' in row_str.upper() or 'EQUALS' in row_str.upper():
                    amt = re.search(r'\$?([\d,]+\.\d{2})', row_str)
                    if amt:
                        try:
                            closing_balance = float(amt.group(1).replace(',', ''))
                            break
                        except ValueError:
                            pass
        # Opening/Closing date: use closing date year and month (e.g. "Jan 26, 2025" -> 2025, 1)
        if statement_year is None and ('OPENING DATE' in full_text or 'CLOSING DATE' in full_text):
            for match in re.finditer(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+(\d{4})', full_text, re.I):
                statement_year = int(match.group(2))
            # Prefer later year when both Dec 2024 and Jan 2025 appear (closing = Jan 2025)
            if statement_year is not None and 'JAN' in full_text and 'DEC' in full_text:
                for match in re.finditer(r'Jan\s+\d{1,2},?\s+(\d{4})', full_text, re.I):
                    statement_year = int(match.group(1))
                    closing_month = 1
                    break
        if opening_balance is not None and closing_balance is not None and statement_year is not None:
            break

    if statement_year is None:
        statement_year = 2025

    # 2) Collect transaction tables (tables with "Your Transactions" and "Amount ($)")
    for ti, t in enumerate(tables):
        df = t.df.fillna('')
        if len(df) < 4:
            continue
        full_text = ' '.join(df.values.astype(str).flatten().tolist()).upper()
        if 'YOUR TRANSACTIONS' not in full_text or 'AMOUNT' not in full_text:
            continue

        # Find header row (Transaction Date, Posting Date, Details, Amount)
        start_row = 0
        for idx in range(min(5, len(df))):
            row_text = ' '.join([str(x) for x in df.iloc[idx].tolist()]).upper()
            if 'TRANSACTION' in row_text and ('POSTING' in row_text or 'DATE' in row_text) and 'AMOUNT' in row_text:
                start_row = idx + 1
                break

        ncols = len(df.columns)
        i = start_row
        while i < len(df):
            row = df.iloc[i]
            cells = [str(row.iloc[j]).strip() if j < ncols else '' for j in range(ncols)]
            trans_date_str = cells[0] if len(cells) > 0 else ''
            post_date_str = cells[1] if len(cells) > 1 else ''
            details = (cells[2] if len(cells) > 2 else '').replace('\n', ' ').strip()
            # Layout where date + date + description (or date + description) are all in column 0 (newline-separated)
            if not details and trans_date_str and '\n' in trans_date_str:
                parts = [p.strip() for p in trans_date_str.replace('\r', '\n').split('\n') if p.strip()]
                if len(parts) >= 3 and _parse_date(parts[0], statement_year, closing_month) and _parse_date(parts[1], statement_year, closing_month):
                    details = ' '.join(parts[2:])
                elif len(parts) >= 2 and _parse_date(parts[0], statement_year, closing_month) and not _parse_date(parts[1], statement_year, closing_month):
                    details = ' '.join(parts[1:])
            amount_str = cells[-1].strip() if cells else ''  # amount usually last column
            if ncols > 4:
                if not amount_str and len(cells) > 4:
                    amount_str = (cells[4] if len(cells) > 4 else cells[3]).strip().replace('\n', ' ')
            amount_val = _parse_amount(amount_str)

            # Skip section headers and footers (but INCLUDE Other Account Transactions e.g. MEMBERSHIP FEE so balances match)
            row_upper = (trans_date_str + ' ' + post_date_str + ' ' + details).upper()
            if any(x in row_upper for x in (
                'NEW PAYMENTS', 'TOTAL OF PAYMENT ACTIVITY', 'NEW TRANSACTIONS FOR',
                'CARD NUMBER', 'TOTAL OF NEW TRANSACTIONS', 'REFERENCE AT', 'YOUR TRANSACTIONS',
                'UNITED STATES DOLLAR', 'QATARI RIAL', 'U.A.E. DIRHAM', 'ARRIVAL', 'DEPARTURE', 'NIGHTS',
                'PREPARED FOR', 'ACCOUNT NUMBER', 'OPENING DATE', 'CLOSING DATE',
                'OTHER ACCOUNT TRANSACTIONS', 'TOTAL OF OTHER ACCOUNT'  # skip header/total rows only
            )):
                i += 1
                continue
            if not trans_date_str and not post_date_str and not details and amount_val is None:
                i += 1
                continue

            # Amount on next row(s): current row has date + description, amount may be 1-3 rows below (e.g. after currency line or "Other Account Transactions")
            # Do NOT take amount from summary/total rows (Total of New Transactions, New Balance, etc.)
            def _is_summary_or_total_row(row_text_upper):
                return any(x in row_text_upper for x in (
                    'TOTAL OF NEW TRANSACTIONS', 'EQUALS NEW BALANCE', 'NEW BALANCE',
                    'MINIMUM AMOUNT DUE', 'TOTAL OF OTHER ACCOUNT', 'ACCOUNT SUMMARY',
                    'PREVIOUS BALANCE', 'LESS PAYMENTS', 'PLUS PURCHASES', 'PLUS FEES'
                )) or (row_text_upper.strip() == 'SAIF AL SHAWAF')

            if _parse_date(trans_date_str, statement_year, closing_month) and details and amount_val is None:
                for look in range(1, min(4, len(df) - i)):
                    next_row = df.iloc[i + look]
                    next_cells = [str(next_row.iloc[j]).strip() if j < len(next_row) else '' for j in range(ncols)]
                    next_row_text = ' '.join(next_cells).upper()
                    if _is_summary_or_total_row(next_row_text):
                        continue  # skip this row, try next
                    # If this row is a currency conversion line (e.g. U.A.E. DIRHAM 104.00 0.39), CAD amount is on the row after
                    if any(x in next_row_text for x in ('UNITED STATES DOLLAR', 'U.A.E. DIRHAM', 'QATARI RIAL', 'DIRHAM', 'DOLLAR')) and look == 1 and i + 2 < len(df):
                        row_after = df.iloc[i + 2]
                        cells_after = [str(row_after.iloc[j]).strip() if j < len(row_after) else '' for j in range(ncols)]
                        after_text = ' '.join(cells_after).upper()
                        if _is_summary_or_total_row(after_text):
                            continue
                        for c in range(len(cells_after) - 1, -1, -1):
                            cand = _parse_amount(cells_after[c])
                            if cand is not None:
                                amount_val = cand
                                i += 2
                                break
                        if amount_val is not None:
                            break
                    # Take first parseable amount from this row (use amounts exactly as on statement)
                    for c in range(len(next_cells) - 1, -1, -1):
                        cand = _parse_amount(next_cells[c])
                        if cand is not None:
                            amount_val = cand
                            i += look
                            break
                    if amount_val is not None:
                        break

            if amount_val is not None:
                date_parsed = _parse_date(trans_date_str, statement_year, closing_month) or _parse_date(post_date_str, statement_year, closing_month)
                if date_parsed and details and 'REFERENCE' not in details.upper():
                    transactions.append({
                        'Date': date_parsed,
                        'Description': details,
                        'Amount': amount_val,
                    })
            i += 1

    if not transactions:
        return pd.DataFrame(), opening_balance, closing_balance, statement_year

    out = pd.DataFrame(transactions)
    # Running balance: opening + cumsum(Amount). AMEX: positive = charges, negative = payments
    opening = opening_balance if opening_balance is not None else 0
    out['Running_Balance'] = opening + out['Amount'].cumsum()
    return out, opening_balance, closing_balance, statement_year


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/Shawafy Inc. AMEX Credit Card/1. Jan 2025.pdf"
    df, open_b, close_b, year = extract_amex_statement(path)
    print(f"Opening: {open_b}, Closing: {close_b}, Year: {year}")
    print(f"Transactions: {len(df)}")
    if len(df) > 0:
        print(df.head(10).to_string())
        print("...")
        print(df.tail(5).to_string())
        if close_b is not None and len(df) > 0:
            last_rb = df['Running_Balance'].iloc[-1]
            print(f"\nLast Running_Balance: {last_rb}, Closing: {close_b}, Match: {abs(last_rb - close_b) < 0.02}")
