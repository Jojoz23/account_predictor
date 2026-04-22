#!/usr/bin/env python3
"""Debug repeated transaction extraction blocks in Meridian PDFs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import re
import sys

import camelot
import pandas as pd

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from test_meridian_bank_complete import _find_header, _parse_date, _parse_money, _extract_statement_year


def extract_with_source(pdf_path: Path):
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        full_text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    statement_year = _extract_statement_year(full_text)

    tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")

    rows = []
    current_date: datetime | None = None
    account_section = "deposit"
    pending_description: str | None = None
    opening = None
    closing = None

    for ti, table in enumerate(tables):
        df = table.df.fillna("")
        table_text = " ".join(str(v).strip().lower() for v in df.to_numpy().flatten())
        if "deposit accounts" in table_text or "chequing" in table_text:
            account_section = "deposit"
        if "loan accounts" in table_text:
            account_section = "loan"

        header_row, date_idx, activity_idx, withdrawals_idx, deposits_idx, balance_idx = _find_header(df)
        if header_row < 0:
            continue

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
            if "installment loan" in row_text or re.search(r"\bloans\b", row_text):
                account_section = "loan"
                break

            date_cell = str(row.iloc[date_idx]).strip() if date_idx < len(row) else ""
            activity = str(row.iloc[activity_idx]).strip() if activity_idx < len(row) else ""
            if not activity and not date_cell:
                continue
            activity_lower = activity.lower()
            if any(k in activity_lower for k in ("account totals", "totals", "ytd interest charged", "fees", "interest pd.")):
                continue

            w = _parse_money(row.iloc[withdrawals_idx]) if withdrawals_idx is not None and withdrawals_idx < len(row) else None
            d = _parse_money(row.iloc[deposits_idx]) if deposits_idx is not None and deposits_idx < len(row) else None
            b = _parse_money(row.iloc[balance_idx]) if balance_idx is not None and balance_idx < len(row) else None

            parsed_date = _parse_date(date_cell, statement_year)
            if parsed_date is not None:
                current_date = parsed_date

            if "balance forward" in activity_lower:
                if opening is None and b is not None:
                    opening = b
                continue

            if not date_cell and w is None and d is None and b is None:
                if pending_description and activity:
                    pending_description = (pending_description + " " + activity).strip()
                elif rows and activity:
                    rows[-1]["Description"] = (rows[-1]["Description"] + " " + activity).strip()
                continue

            if current_date is None:
                continue

            if date_cell and activity and w is None and d is None:
                pending_description = activity
                continue

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

            row_obj = {
                "Date": current_date.strftime("%Y-%m-%d"),
                "Description": description,
                "Withdrawals": withdrawals,
                "Deposits": deposits,
                "Balance": b,
                "TableIdx": ti,
                "Page": int(table.page),
                "TableRow": r,
            }
            rows.append(row_obj)
            if b is not None:
                closing = b

    df_out = pd.DataFrame(rows)
    if df_out.empty:
        return df_out, opening, closing
    df_out["Date"] = pd.to_datetime(df_out["Date"], errors="coerce")
    df_out["Withdrawals"] = pd.to_numeric(df_out["Withdrawals"], errors="coerce").fillna(0.0)
    df_out["Deposits"] = pd.to_numeric(df_out["Deposits"], errors="coerce").fillna(0.0)
    df_out["Net_Change"] = df_out["Deposits"] - df_out["Withdrawals"]
    if opening is not None:
        df_out["Running_Balance"] = opening + df_out["Net_Change"].cumsum()
    else:
        df_out["Running_Balance"] = df_out["Net_Change"].cumsum()
    return df_out, opening, closing


def find_longest_block(df: pd.DataFrame):
    if df.empty:
        return None
    keys = ["Date", "Description", "Withdrawals", "Deposits", "Balance"]
    wrk = df[keys].copy()
    wrk["Date"] = pd.to_datetime(wrk["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for c in ["Withdrawals", "Deposits", "Balance"]:
        wrk[c] = pd.to_numeric(wrk[c], errors="coerce").round(2)
    wrk = wrk.fillna("")
    sig = ["|".join(str(r[c]) for c in keys) for _, r in wrk.iterrows()]
    n = len(sig)
    best = None
    for L in range(min(120, n // 2), 1, -1):
        groups = defaultdict(list)
        for i in range(0, n - L + 1):
            groups[tuple(sig[i : i + L])].append(i)
        for starts in groups.values():
            if len(starts) > 1:
                best = (L, starts)
                return best
    return best


def main():
    folder = Path("data/Burger Factory/meridian")
    targets = [
        "3. Mar 2025.pdf",
        "6. Jun 2025.pdf",
        "7. Jul 2025.pdf",
        "8. Aug 2025.pdf",
        "9. Sep 2025.pdf",
        "10. Oct 2025.pdf",
    ]
    for name in targets:
        pdf = folder / name
        print("\n" + "=" * 100)
        print(name)
        df, opening, closing = extract_with_source(pdf)
        if df.empty:
            print("No extracted rows")
            continue
        final_rb = float(df["Running_Balance"].iloc[-1])
        diff = abs(final_rb - float(closing)) if closing is not None else None
        print(f"rows={len(df)} opening={opening} closing={closing} final_rb={final_rb:.2f} diff={diff:.2f}")

        best = find_longest_block(df)
        if not best:
            print("No repeated contiguous block found.")
            continue
        L, starts = best
        print(f"longest repeated block length={L} starts={starts[:3]}")
        s1, s2 = starts[0], starts[1]
        cols = ["Date", "Description", "Withdrawals", "Deposits", "Balance", "Page", "TableIdx", "TableRow"]
        print("-- first occurrence --")
        print(df.loc[s1 : s1 + min(L - 1, 8), cols].to_string(index=True))
        print("-- second occurrence --")
        print(df.loc[s2 : s2 + min(L - 1, 8), cols].to_string(index=True))


if __name__ == "__main__":
    main()

