#!/usr/bin/env python3
"""
Trace through the pdf_to_quickbooks pipeline to find where the second transaction is lost
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import extract_from_pdf
from pdf_to_quickbooks import PDFToQuickBooks
import pandas as pd

def trace_pdf_to_quickbooks():
    print("🔍 TRACING PDF_TO_QUICKBOOKS PIPELINE")
    print("="*60)
    
    pdf_path = "data/1. Jan 31st 2022.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    # Step 1: Raw extraction
    print("\n📋 STEP 1: Raw extraction")
    raw_df = extract_from_pdf(pdf_path)
    
    if raw_df is not None and not raw_df.empty:
        print(f"✅ Raw extraction: {len(raw_df)} transactions")
        
        # Check Holland Leasing
        holland = raw_df[raw_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        jan21 = holland[holland['Date'].astype(str).str.contains('2022-01-21', na=False)]
        
        print(f"🏢 Jan 21 Holland Leasing after raw extraction: {len(jan21)}")
        if len(jan21) > 0:
            for i, (_, row) in enumerate(jan21.iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {row.get('Deposits', 'N/A')}")
                print(f"     Balance: {row.get('Balance', 'N/A')}")
                print()
    else:
        print("❌ Raw extraction failed")
        return
    
    # Step 2: Convert to standard format
    print("\n📋 STEP 2: Convert to standard format")
    pipeline = PDFToQuickBooks()
    standard_df, was_credit_card = pipeline._convert_to_standard_format(raw_df.copy())
    
    if standard_df is not None and not standard_df.empty:
        print(f"✅ Standard format: {len(standard_df)} transactions")
        
        # Check Holland Leasing
        holland = standard_df[standard_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        jan21 = holland[holland['Date'].astype(str).str.contains('2022-01-21', na=False)]
        
        print(f"🏢 Jan 21 Holland Leasing after conversion: {len(jan21)}")
        if len(jan21) > 0:
            for i, (_, row) in enumerate(jan21.iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Amount: {row.get('Amount', 'N/A')}")
                print(f"     Balance: {row.get('Balance', 'N/A')}")
                print()
    else:
        print("❌ Standard format conversion failed")
        return

if __name__ == "__main__":
    trace_pdf_to_quickbooks()


