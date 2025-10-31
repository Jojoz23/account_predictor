#!/usr/bin/env python3
import sys
from pathlib import Path
import re
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from extract_bank_statements import BankStatementExtractor  # noqa: E402


def parse_money(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace('$', '').replace(',', '')
    try:
        return float(s)
    except Exception:
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools/analyze_statement.py <pdf_path> <excel_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    excel_path = sys.argv[2]

    print(f"PDF:   {pdf_path}")
    print(f"Excel: {excel_path}")

    # Analyze PDF using extractor internals
    extractor = BankStatementExtractor(pdf_path)
    # Detect bank/year via detection logic
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            sample = pdf.pages[0].extract_text() if pdf.pages else ''
        extractor._detect_bank(sample)  # type: ignore
    except Exception:
        pass

    opening, closing = extractor._extract_opening_closing_balances()  # type: ignore
    year = extractor.metadata.get('statement_year')
    bank = extractor.metadata.get('bank')

    print(f"Bank: {bank}")
    print(f"Statement year (detected): {year}")
    print(f"Opening (PDF): {opening}")
    print(f"Closing (PDF): {closing}")

    # Read Excel
    df = pd.read_excel(excel_path, sheet_name='Categorized Transactions')
    # Dates
    years = sorted(pd.to_datetime(df['Date'], errors='coerce').dt.year.dropna().unique().tolist())
    print(f"Years in Excel Date: {years}")

    # Running Total first/last
    if 'Running Total' in df.columns:
        first_rt = parse_money(df['Running Total'].iloc[0])
        last_rt = parse_money(df['Running Total'].iloc[-1])
        print(f"Running Total first: {first_rt}")
        print(f"Running Total last:  {last_rt}")
        if opening is not None:
            print(f"Opening match: {abs(first_rt - opening) < 0.01 if first_rt is not None else False}")
        if closing is not None:
            print(f"Closing match: {abs(last_rt - closing) < 0.01 if last_rt is not None else False}")
    else:
        print("Running Total column missing in Excel")

    # Amount cumulative cross-check (display sign convention for bank accounts)
    if 'Amount' in df.columns:
        amt_sum = df['Amount'].sum()
        print(f"Sum of Amount (AI sign convention): {amt_sum}")

    print("Done.")


if __name__ == '__main__':
    main()



