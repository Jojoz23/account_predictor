#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test single TD bank - 7206 file"""

from test_td_bank_complete import extract_td_bank_statement_camelot
import pandas as pd

pdf_path = "data/TD bank - 7206/TD Investors 5047206 - February 28 2025.pdf"

print(f"Testing: {pdf_path}")
print("="*70)

df, op, cl, yr = extract_td_bank_statement_camelot(pdf_path)

print(f"\nResults:")
print(f"Transactions: {len(df) if df is not None else 0}")
print(f"Opening: {op}")
print(f"Closing: {cl}")

if df is not None and len(df) > 0:
    if 'Running_Balance' in df.columns:
        print(f"Final Running Balance: ${df['Running_Balance'].iloc[-1]:,.2f}")
    print(f"\nAll transactions:")
    print(df.to_string())
else:
    print("No transactions extracted")


