#!/usr/bin/env python3
import os
from pathlib import Path
from extract_bank_statements import extract_from_pdf

def main():
    folder = Path('data/Test Statements')
    pdfs = [p for p in folder.iterdir() if p.suffix.lower() == '.pdf']
    if not pdfs:
        print('No PDFs found in data/Test Statements')
        return
    print(f'Found {len(pdfs)} test PDFs')
    for i, pdf in enumerate(sorted(pdfs), 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf.name}")
        df = extract_from_pdf(str(pdf), save_excel=False)
        if df is None or df.empty:
            print('  ❌ Extraction failed or empty')
            continue
        has_rb = 'Running_Balance' in df.columns
        print(f"  Rows: {len(df)}  Running_Balance present: {has_rb}")
        if has_rb:
            print(f"  First RB: {df['Running_Balance'].iloc[0]:,.2f}  Last RB: {df['Running_Balance'].iloc[-1]:,.2f}")

if __name__ == '__main__':
    main()



