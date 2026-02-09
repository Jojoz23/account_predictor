#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test September statement only"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from test_td_bank_complete import extract_td_bank_statement_camelot

pdf_path = "data/TD bank - 4738/9. TD 5044738 - September 29 2025.pdf"

print("Testing September statement...")
df, opening, closing, year = extract_td_bank_statement_camelot(pdf_path)

print(f"\nResults:")
print(f"  Transactions: {len(df) if df is not None else 0}")
print(f"  Opening: ${opening:,.2f}" if opening else "  Opening: Not found")
print(f"  Closing: ${closing:,.2f}" if closing else "  Closing: Not found")
print(f"  Expected: Opening=$325.75, Closing=$695.74")

if df is not None and len(df) > 0:
    print(f"\nFirst 5 transactions:")
    print(df[['Date', 'Description', 'Withdrawals', 'Deposits']].head(5).to_string())
    print(f"\nLast 5 transactions:")
    print(df[['Date', 'Description', 'Withdrawals', 'Deposits']].tail(5).to_string())



