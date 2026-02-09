#!/usr/bin/env python3
"""
Run AMEX (Camelot) extraction on all PDFs in data/Shawafy Inc. AMEX Credit Card.
Reports pass/fail and balance match per file.
"""
from pathlib import Path
from test_amex_complete import extract_amex_statement

FOLDER = Path(__file__).resolve().parent / "data" / "Shawafy Inc. AMEX Credit Card"

def main():
    if not FOLDER.exists():
        print(f"Folder not found: {FOLDER}")
        return
    pdfs = sorted(FOLDER.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {FOLDER}")
        return
    print(f"Found {len(pdfs)} PDFs in {FOLDER.name}\n")
    passed = 0
    failed = 0
    for pdf_path in pdfs:
        try:
            df, open_b, close_b, year = extract_amex_statement(str(pdf_path))
            n = len(df)
            if n == 0:
                print(f"FAIL {pdf_path.name}: no transactions")
                failed += 1
                continue
            last_rb = df["Running_Balance"].iloc[-1]
            match = close_b is not None and abs(last_rb - close_b) < 0.02
            status = "PASS" if match else "BALANCE_MISMATCH"
            if match:
                passed += 1
            else:
                failed += 1
            print(f"{status} {pdf_path.name}  transactions={n}  open={open_b}  close={close_b}  last_rb={last_rb:.2f}")
        except Exception as e:
            print(f"FAIL {pdf_path.name}: {e}")
            failed += 1
    print(f"\nTotal: {passed} passed, {failed} failed")

if __name__ == "__main__":
    main()
