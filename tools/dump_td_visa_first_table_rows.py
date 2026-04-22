#!/usr/bin/env python3
"""Dump first Camelot table rows for TD Visa statements."""

from pathlib import Path
import re

import camelot


FILES = [
    "1. Jan 2025.pdf",
    "2. Feb 2025.pdf",
    "4. Apr 2025.pdf",
    "7. Jul 2025.pdf",
    "8. Aug 2025.pdf",
    "10. Oct 2025.pdf",
    "12. Dec 2025.pdf",
]


def find_header_row(df):
    for i in range(len(df)):
        row_text = " ".join(str(c).upper() for c in df.iloc[i].tolist())
        if (
            "DATE" in row_text
            and "AMOUNT" in row_text
            and (
                "DESCRIPTION" in row_text
                or "ACTIVITY" in row_text
                or "MERCHANT" in row_text
                or "DETAILS" in row_text
            )
        ):
            return i
    return None


def main() -> int:
    base = Path("data/Burger Factory/td visa")
    out = base / "td_visa_first_table_rows_report.txt"

    lines = []
    for name in FILES:
        pdf = base / name
        if not pdf.exists():
            lines.append(f"\n=== {name} ===\nMISSING FILE\n")
            continue

        tables = camelot.read_pdf(str(pdf), pages="1", flavor="stream")
        lines.append(f"\n=== {name} ===")
        lines.append(f"tables_on_page1={len(tables)}")
        if not tables:
            lines.append("NO TABLES FOUND")
            continue

        df = tables[0].df.fillna("")
        header_row = find_header_row(df)
        lines.append(f"first_table_shape={df.shape}")
        lines.append(f"detected_header_row={header_row}")
        lines.append("rows:")
        for i in range(len(df)):
            row = " || ".join(str(x).replace("\n", "\\n") for x in df.iloc[i].tolist())
            mark = "  <-- HEADER" if header_row is not None and i == header_row else ""
            lines.append(f"{i:03d}: {row}{mark}")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

