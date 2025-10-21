#!/usr/bin/env python3
"""
Trace the full extraction to see exactly where the second transaction is lost
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def trace_full_extraction():
    print("🔍 TRACING FULL EXTRACTION")
    print("="*50)
    
    pdf_path = "data/1. Jan 31st 2022.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    # Create extractor
    extractor = BankStatementExtractor(pdf_path)
    
    # Call extract and check what it returns
    print("\n📋 Calling extractor.extract()...")
    result = extractor.extract()
    
    if result is not None and not result.empty:
        print(f"✅ Extract returned: {len(result)} transactions")
        print(f"Columns: {list(result.columns)}")
        
        # Check Holland Leasing in the result
        holland = result[result['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        print(f"\n🏢 Total Holland Leasing in result: {len(holland)}")
        
        jan21_holland = holland[holland['Date'].astype(str).str.contains('2022-01-21', na=False)]
        print(f"Jan 21 Holland Leasing in result: {len(jan21_holland)}")
        
        if len(jan21_holland) > 0:
            print(f"\n📋 Jan 21 Holland Leasing transactions:")
            for i, (_, row) in enumerate(jan21_holland.iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Description: {row.get('Description', 'N/A')}")
                print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {row.get('Deposits', 'N/A')}")
                print(f"     Balance: {row.get('Balance', 'N/A')}")
                print()
        
        # Show all transactions to see if we can spot the missing one
        print(f"\n📋 All transactions (showing first 10 and last 10):")
        print(result[['Date', 'Description', 'Withdrawals', 'Balance']].head(10).to_string())
        print("...")
        print(result[['Date', 'Description', 'Withdrawals', 'Balance']].tail(10).to_string())
    else:
        print("❌ Extract returned None or empty DataFrame")

if __name__ == "__main__":
    trace_full_extraction()


