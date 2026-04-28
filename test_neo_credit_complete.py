#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo Credit Card statement parser (Camelot-first).
"""

from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

import camelot
import pandas as pd
import pdfplumber


MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_money(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = text.replace(",", "").replace("$", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except Exception:
        return None


def _extract_statement_year(page_text: str) -> Optional[int]:
    # Example: "May 31, 2025 - Jun 27, 2025"
    m = re.search(r"[A-Za-z]{3,9}\s+\d{1,2},\s+(\d{4})\s*-\s*[A-Za-z]{3,9}\s+\d{1,2},\s+(\d{4})", page_text)
    if m:
        return int(m.group(2))
    return None


def _extract_balances(page_text: str) -> Tuple[Optional[float], Optional[float]]:
    opening = None
    closing = None

    prev_match = re.search(r"Previous Amount Owing\s+([0-9,]+\.[0-9]{2})", page_text)
    new_match = re.search(r"New Amount Owing\s+([0-9,]+\.[0-9]{2})", page_text)
    if prev_match:
        opening = _parse_money(prev_match.group(1))
    if new_match:
        closing = _parse_money(new_match.group(1))
    return opening, closing


def _parse_date(mon_day: str, statement_year: Optional[int]) -> pd.Timestamp:
    m = re.match(r"^([A-Za-z]{3})\s+(\d{1,2})$", mon_day.strip())
    if not m:
        return pd.NaT
    month = MONTH_MAP.get(m.group(1).lower())
    day = int(m.group(2))
    year = statement_year or datetime.now().year
    if not month:
        return pd.NaT
    try:
        return pd.Timestamp(year=year, month=month, day=day)
    except Exception:
        return pd.NaT


def extract_neo_credit_statement(pdf_path: str):
    """
    Returns:
      df: Date, Description, Amount, Running_Balance
      opening_balance: float|None
      closing_balance: float|None
      statement_year: str|None
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    with pdfplumber.open(str(path)) as pdf:
        first_page_text = pdf.pages[0].extract_text() if pdf.pages else ""

    statement_year = _extract_statement_year(first_page_text or "")
    opening_balance, closing_balance = _extract_balances(first_page_text or "")

    tables = camelot.read_pdf(str(path), pages="all", flavor="stream")
    transactions = []

    for table in tables:
        df = table.df.fillna("")
        for _, row in df.iterrows():
            vals = [str(v).strip() for v in row.tolist()]
            if len(vals) < 4:
                continue

            # Neo layout is: Transaction Date | Posted Date | Description | Amount
            # Use Transaction Date for bookkeeping Date field (never Posted Date).
            trans_date = vals[0]
            posted_date = vals[1]
            desc = vals[2]
            amount_str = vals[-1]

            if not re.match(r"^[A-Za-z]{3}\s+\d{1,2}$", trans_date):
                continue
            if not re.match(r"^[A-Za-z]{3}\s+\d{1,2}$", posted_date):
                continue
            if not re.search(r"-?[0-9,]+\.[0-9]{2}$", amount_str):
                continue

            raw_amount = _parse_money(amount_str)
            if raw_amount is None:
                continue

            # Neo tables show payments as positive and purchases as negative.
            # Normalize to bookkeeping convention: charges positive, payments negative.
            normalized_amount = -raw_amount

            tx_date = _parse_date(trans_date, statement_year)
            if pd.isna(tx_date):
                continue

            transactions.append({
                "Date": tx_date,
                "Description": re.sub(r"\s+", " ", desc).strip(),
                "Amount": normalized_amount,
            })

    if not transactions:
        raise ValueError("No Neo transactions extracted")

    out = pd.DataFrame(transactions)
    out = out.sort_values("Date").reset_index(drop=True)

    if opening_balance is not None:
        out["Running_Balance"] = opening_balance + out["Amount"].cumsum()
    else:
        out["Running_Balance"] = out["Amount"].cumsum()

    return out, opening_balance, closing_balance, (str(statement_year) if statement_year else None)


if __name__ == "__main__":
    pdf_dir = Path("data/neo cc")
    files = sorted(pdf_dir.glob("*.pdf"))
    if not files:
        print("No Neo PDFs found in data/neo cc")
        raise SystemExit(1)

    sample = files[0]
    df, opening, closing, year = extract_neo_credit_statement(str(sample))
    print(f"File: {sample.name}")
    print(f"Transactions: {len(df)}")
    print(f"Opening: {opening}")
    print(f"Closing: {closing}")
    print(f"Year: {year}")
    print(df.head(10).to_string(index=False))
