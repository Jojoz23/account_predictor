#!/usr/bin/env python3
"""
Explore Meridian bank PDF structure (Camelot-first).

Usage:
  python explore_meridian_bank.py
  python explore_meridian_bank.py "data/Burger Factory/meridian/1. Jan 2025.pdf"
"""

from pathlib import Path
import sys
import re
import pdfplumber
import camelot


def _print_text_snippet(pdf_path: Path, max_chars: int = 5000) -> None:
    with pdfplumber.open(str(pdf_path)) as pdf:
        print(f"Pages: {len(pdf.pages)}")
        first = pdf.pages[0].extract_text() or ""
        print("\n--- PAGE 1 TEXT (snippet) ---")
        print(first[:max_chars])
        print("--- END PAGE 1 TEXT ---\n")

        full_text = "\n".join((pg.extract_text() or "") for pg in pdf.pages[: min(3, len(pdf.pages))])
        patterns = {
            "statement_period": r"(Statement\s+Period|From\s+.*\s+to\s+.*)",
            "opening_balance": r"(Opening\s+Balance|Balance\s+Forward)",
            "closing_balance": r"(Closing\s+Balance|New\s+Balance|Ending\s+Balance)",
            "account_number": r"(Account\s*(Number|No\.?)\s*[:#]?\s*[A-Za-z0-9\-]+)",
        }
        print("--- HEADER PATTERN HITS (first 3 pages) ---")
        for label, pat in patterns.items():
            m = re.findall(pat, full_text, flags=re.IGNORECASE)
            print(f"{label}: {len(m)} hit(s)")
        print()


def _print_camelot_tables(pdf_path: Path) -> None:
    print("--- CAMELOT STREAM TABLES ---")
    tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")
    print(f"Total tables: {len(tables)}\n")

    for i, table in enumerate(tables[:10]):
        df = table.df.fillna("")
        print(f"[Table {i+1}] page={table.page} shape={df.shape}")
        print(df.head(12).to_string(index=False, header=False))
        print("-" * 90)


def main() -> int:
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        folder = Path("data/Burger Factory/meridian")
        pdfs = sorted(folder.glob("*.pdf"))
        if not pdfs:
            print(f"No PDFs found in {folder}")
            return 1
        target = pdfs[0]

    if not target.exists():
        print(f"File not found: {target}")
        return 1

    print("=" * 100)
    print(f"EXPLORING: {target}")
    print("=" * 100)
    _print_text_snippet(target)
    _print_camelot_tables(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

