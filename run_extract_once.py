#!/usr/bin/env python3
from extract_bank_statements import extract_from_pdf

def main():
    pdf = 'data/Bank Statements/7. October 2023.pdf'
    out = 'data/extracted_7. October 2023_cleaned.xlsx'
    print('Running extraction for:', pdf)
    df = extract_from_pdf(pdf, save_excel=True, output_path=out)
    if df is None:
        print('Extraction returned None')
    else:
        print('Rows:', len(df))
    print('Saved to:', out)

if __name__ == '__main__':
    main()


