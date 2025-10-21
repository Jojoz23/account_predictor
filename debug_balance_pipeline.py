#!/usr/bin/env python3
"""
Debug the Balance column through the entire pipeline
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
from pdf_to_quickbooks import PDFToQuickBooks
import pandas as pd

def debug_balance_pipeline():
    print("🔍 DEBUGGING BALANCE COLUMN THROUGH PIPELINE")
    print("="*60)
    
    pdf_path = "data/1. Jan 31st 2022.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    # Step 1: Raw extraction
    print("\n📋 STEP 1: Raw extraction")
    extractor = BankStatementExtractor(pdf_path)
    raw_df = extractor.extract()
    
    if raw_df is not None and not raw_df.empty:
        print(f"✅ Raw extraction: {len(raw_df)} transactions")
        print(f"Columns: {list(raw_df.columns)}")
        
        # Check Holland Leasing with Balance
        holland = raw_df[raw_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        jan21_holland = holland[holland['Date'].astype(str).str.contains('2022-01-21', na=False)]
        
        print(f"\n🏢 Jan 21 Holland Leasing in raw data: {len(jan21_holland)}")
        if len(jan21_holland) > 0:
            for i, (_, row) in enumerate(jan21_holland.iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Description: {row.get('Description', 'N/A')}")
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
    standard_df, was_credit_card = pipeline._convert_to_standard_format(raw_df)
    
    if standard_df is not None and not standard_df.empty:
        print(f"✅ Standard format: {len(standard_df)} transactions")
        print(f"Columns: {list(standard_df.columns)}")
        
        # Check Holland Leasing with Balance
        holland = standard_df[standard_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        jan21_holland = holland[holland['Date'].astype(str).str.contains('2022-01-21', na=False)]
        
        print(f"\n🏢 Jan 21 Holland Leasing in standard format: {len(jan21_holland)}")
        if len(jan21_holland) > 0:
            for i, (_, row) in enumerate(jan21_holland.iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Description: {row.get('Description', 'N/A')}")
                print(f"     Amount: {row.get('Amount', 'N/A')}")
                print(f"     Balance: {row.get('Balance', 'N/A')}")
                print()
    else:
        print("❌ Standard format conversion failed")
        return
    
    # Step 3: Check if Balance is being used in deduplication
    print("\n📋 STEP 3: Check deduplication logic")
    
    # Check if there are duplicates that should be kept separate
    duplicate_subset = ['Date', 'Description', 'Amount']
    if 'Balance' in standard_df.columns:
        duplicate_subset.append('Balance')
        print(f"✅ Balance column included in deduplication: {duplicate_subset}")
    else:
        print(f"❌ Balance column missing from deduplication: {duplicate_subset}")
    
    # Check for potential duplicates
    potential_duplicates = standard_df[standard_df.duplicated(subset=['Date', 'Description', 'Amount'], keep=False)]
    print(f"Potential duplicates (same date/description/amount): {len(potential_duplicates)}")
    
    if len(potential_duplicates) > 0:
        print(f"\n📋 Potential duplicates:")
        for i, (_, row) in enumerate(potential_duplicates.head(5).iterrows()):
            print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
            print(f"     Description: {row.get('Description', 'N/A')}")
            print(f"     Amount: {row.get('Amount', 'N/A')}")
            print(f"     Balance: {row.get('Balance', 'N/A')}")
            print()

if __name__ == "__main__":
    debug_balance_pipeline()

