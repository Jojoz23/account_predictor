#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test September 7206 file"""

from test_td_bank_complete import extract_td_bank_statement_camelot

pdf_path = "data/TD bank - 7206/TD Investors 5047206 - September 29 2025.pdf"

df, opening, closing, year = extract_td_bank_statement_camelot(pdf_path)

print(f"Transactions: {len(df) if df is not None else 0}")
print(f"Opening: {opening}")
print(f"Closing: {closing}")

if df is not None and len(df) > 0:
    print("\nTransactions:")
    print(df[['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance', 'Running_Balance']].to_string())
    if 'Running_Balance' in df.columns:
        print(f"\nFinal Running Balance: ${df['Running_Balance'].iloc[-1]:,.2f}")
        if closing:
            diff = df['Running_Balance'].iloc[-1] - closing
            print(f"Difference: ${diff:,.2f}")



