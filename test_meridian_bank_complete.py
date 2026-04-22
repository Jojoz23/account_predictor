#!/usr/bin/env python3
"""
Camelot-first extraction for Meridian bank statements (chequing).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import camelot
import pandas as pd
import pdfplumber


def _parse_money(value: object) -> float | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    if not s:
        return None

    sign = 1.0
    if s.startswith("(") and s.endswith(")"):
        sign = -1.0
        s = s[1:-1]
    if s.endswith("OD") or s.endswith("DR"):
        sign = -1.0
        s = s[:-2]
    elif s.endswith("CR"):
        sign = 1.0
        s = s[:-2]

    s = s.replace("$", "").replace(",", "").replace(" ", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    n = float(m.group(0))
    if n < 0:
        return n
    return sign * n


def _extract_statement_year(full_text: str) -> int | None:
    m = re.search(r"Statement Period Ending:\s+[A-Za-z]+\s+\d{1,2},\s*(\d{4})", full_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"Statement\s+Period\s+Ending:\s*(\d{4}-\d{2}-\d{2})", full_text, re.IGNORECASE)
    if m:
        return int(m.group(1)[:4])
    return None


def _parse_date(text: str, statement_year: int | None) -> datetime | None:
    if not text:
        return None
    s = str(text).strip()
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # Handle "31-Dec-2024" variants already covered; fallback for month words.
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{2,4})$", s)
    if m:
        day = int(m.group(1))
        mon = m.group(2).title()
        yr = int(m.group(3))
        if yr < 100:
            yr += 2000
        try:
            return datetime.strptime(f"{day:02d}-{mon}-{yr}", "%d-%b-%Y")
        except Exception:
            return None
    # If date appears without year, use statement year.
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})$", s)
    if m and statement_year:
        try:
            return datetime.strptime(f"{int(m.group(1)):02d}-{m.group(2).title()}-{statement_year}", "%d-%b-%Y")
        except Exception:
            return None
    return None


def _find_header(df: pd.DataFrame) -> tuple[int, int, int | None, int | None, int | None]:
    header_row = -1
    date_idx = activity_idx = withdrawals_idx = deposits_idx = balance_idx = None

    for i in range(min(len(df), 20)):
        row = [str(x).strip().lower() for x in df.iloc[i].tolist()]
        row_text = " ".join(row)
        if "date" in row_text and "activity" in row_text and "balance" in row_text:
            header_row = i
            for j, cell in enumerate(row):
                if date_idx is None and "date" in cell:
                    date_idx = j
                if activity_idx is None and "activity" in cell:
                    activity_idx = j
                if withdrawals_idx is None and "withdraw" in cell:
                    withdrawals_idx = j
                if deposits_idx is None and "deposit" in cell:
                    deposits_idx = j
                if balance_idx is None and "balance" in cell:
                    balance_idx = j
            break

    return header_row, date_idx or 0, activity_idx or 1, withdrawals_idx, deposits_idx, balance_idx


def extract_meridian_bank_statement(pdf_path: str):
    """
    Returns:
      df, opening_balance, closing_balance, statement_year
    """
    pdf_file = Path(pdf_path)
    with pdfplumber.open(str(pdf_file)) as pdf:
        full_text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)

    statement_year = _extract_statement_year(full_text)

    tables = camelot.read_pdf(str(pdf_file), pages="all", flavor="stream")

    transactions: list[dict] = []
    opening_balance = None
    closing_balance = None
    current_date: datetime | None = None
    account_section = "deposit"
    pending_description: str | None = None
    seen_table_fingerprints: set[tuple[int, str]] = set()

    for table in tables:
        df = table.df.fillna("")
        table_text = " ".join(str(v).strip().lower() for v in df.to_numpy().flatten())

        # Keep only deposit/chequing account section; skip loan account section.
        if "deposit accounts" in table_text or "chequing" in table_text:
            account_section = "deposit"
        if "loan accounts" in table_text:
            account_section = "loan"

        header_row, date_idx, activity_idx, withdrawals_idx, deposits_idx, balance_idx = _find_header(df)
        if header_row < 0:
            continue

        # Camelot can return the same table twice on a page.
        # Deduplicate by page + normalized table-body fingerprint.
        body_rows = []
        for rr in range(header_row + 1, len(df)):
            vals = [str(v).strip().lower() for v in df.iloc[rr].tolist()]
            row_norm = " | ".join(v for v in vals if v)
            if row_norm:
                body_rows.append(row_norm)
        table_fingerprint = "\n".join(body_rows)
        fp_key = (int(table.page), table_fingerprint)
        if table_fingerprint and fp_key in seen_table_fingerprints:
            continue
        seen_table_fingerprints.add(fp_key)

        # Loan tables generally expose principal/interest headers, not withdrawals/deposits.
        if withdrawals_idx is None and deposits_idx is None:
            header_text = " ".join(str(v).strip().lower() for v in df.iloc[header_row].tolist())
            if "principal" in header_text or "interest" in header_text:
                account_section = "loan"
                continue

        if account_section == "loan":
            continue

        for r in range(header_row + 1, len(df)):
            row = df.iloc[r]
            row_text = " ".join(str(v).strip().lower() for v in row.tolist())

            # Mixed page/table: deposit rows first, then Loans subsection.
            if "installment loan" in row_text or re.search(r"\bloans\b", row_text):
                account_section = "loan"
                break

            date_cell = str(row.iloc[date_idx]).strip() if date_idx < len(row) else ""
            activity = str(row.iloc[activity_idx]).strip() if activity_idx < len(row) else ""
            if not activity and not date_cell:
                continue
            activity_lower = activity.lower()

            # Skip statement summary rows (not real transactions).
            if any(k in activity_lower for k in ("account totals", "totals", "ytd interest charged", "fees", "interest pd.")):
                continue

            w = _parse_money(row.iloc[withdrawals_idx]) if withdrawals_idx is not None and withdrawals_idx < len(row) else None
            d = _parse_money(row.iloc[deposits_idx]) if deposits_idx is not None and deposits_idx < len(row) else None
            b = _parse_money(row.iloc[balance_idx]) if balance_idx is not None and balance_idx < len(row) else None

            parsed_date = _parse_date(date_cell, statement_year)
            if parsed_date is not None:
                current_date = parsed_date

            # Balance forward row sets statement opening balance only once.
            if "balance forward" in activity_lower:
                if opening_balance is None and b is not None:
                    opening_balance = b
                continue

            # Continuation description row (no date/amounts/balance)
            if not date_cell and w is None and d is None and b is None:
                if pending_description and activity:
                    pending_description = (pending_description + " " + activity).strip()
                elif transactions and activity:
                    transactions[-1]["Description"] = (transactions[-1]["Description"] + " " + activity).strip()
                continue

            if current_date is None:
                continue

            # Some statements split description and amount across lines:
            # first line has date/description only, next line has amounts.
            if date_cell and activity and w is None and d is None:
                pending_description = activity
                continue

            # No movement -> informational line, skip
            if w is None and d is None:
                continue

            withdrawals = abs(w) if w is not None and w != 0 else 0.0
            deposits = 0.0
            if d is not None and d != 0:
                if d > 0:
                    deposits = d
                else:
                    withdrawals += abs(d)

            description = activity
            if not date_cell and pending_description:
                description = f"{pending_description} {activity}".strip() if activity else pending_description
            pending_description = None

            tx = {
                "Date": current_date.strftime("%Y-%m-%d"),
                "Description": description,
                "Withdrawals": withdrawals,
                "Deposits": deposits,
                "Balance": b,
            }
            transactions.append(tx)
            if b is not None:
                closing_balance = b

    if not transactions:
        return pd.DataFrame(), opening_balance, closing_balance, statement_year

    df_out = pd.DataFrame(transactions)
    df_out["Date"] = pd.to_datetime(df_out["Date"], errors="coerce")
    df_out["Withdrawals"] = pd.to_numeric(df_out["Withdrawals"], errors="coerce").fillna(0.0)
    df_out["Deposits"] = pd.to_numeric(df_out["Deposits"], errors="coerce").fillna(0.0)
    df_out["Balance"] = pd.to_numeric(df_out["Balance"], errors="coerce")

    df_out["Net_Change"] = df_out["Deposits"] - df_out["Withdrawals"]

    if opening_balance is not None:
        df_out["Running_Balance"] = opening_balance + df_out["Net_Change"].cumsum()
    else:
        df_out["Running_Balance"] = df_out["Net_Change"].cumsum()

    if closing_balance is None and "Balance" in df_out.columns:
        last_bal = df_out["Balance"].dropna()
        if len(last_bal):
            closing_balance = float(last_bal.iloc[-1])

    return df_out, opening_balance, closing_balance, statement_year


if __name__ == "__main__":
    folder = Path("data/Burger Factory/meridian")
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {folder}")
        raise SystemExit(1)
    df, opening, closing, year = extract_meridian_bank_statement(str(pdfs[0]))
    print(f"File: {pdfs[0].name}")
    print(f"Rows: {len(df)} | Opening: {opening} | Closing: {closing} | Year: {year}")
    if not df.empty:
        print(df[["Date", "Description", "Withdrawals", "Deposits", "Running_Balance"]].head(20).to_string(index=False))

