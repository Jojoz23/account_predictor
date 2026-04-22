#!/usr/bin/env python3
"""Test Meridian bank extractor on all statements."""

from pathlib import Path
import sys
import io

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

from test_meridian_bank_complete import extract_meridian_bank_statement


def main():
    folder = Path("data/Burger Factory/meridian")
    pdf_files = sorted(folder.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {folder}")
        return

    print("=" * 80)
    print("TESTING ALL MERIDIAN BANK STATEMENTS")
    print("=" * 80)
    print(f"Found {len(pdf_files)} PDF file(s)\n")

    ok = 0
    for pdf in pdf_files:
        print("-" * 80)
        print(f"Testing: {pdf.name}")
        try:
            df, opening, closing, year = extract_meridian_bank_statement(str(pdf))
            if df is None or df.empty:
                print("  ❌ No transactions extracted")
                continue
            final_rb = float(df["Running_Balance"].iloc[-1]) if "Running_Balance" in df.columns else None
            print(f"  Rows: {len(df)}")
            print(f"  Opening: {opening}")
            print(f"  Closing: {closing}")
            print(f"  Final RB: {final_rb}")
            if final_rb is not None and closing is not None:
                diff = abs(final_rb - float(closing))
                if diff < 0.01:
                    print("  ✅ Running balance matches closing balance")
                    ok += 1
                else:
                    print(f"  WARN Difference: {diff:.2f}")
            else:
                print("  WARN Missing opening/closing or running balance")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n" + "=" * 80)
    print(f"Passed balance checks: {ok}/{len(pdf_files)}")
    print("=" * 80)


if __name__ == "__main__":
    main()

