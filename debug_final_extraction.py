#!/usr/bin/env python3
"""
Debug the final extraction step to see where the second transaction is lost
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def debug_final_extraction():
    print("🔍 DEBUGGING FINAL EXTRACTION STEP")
    print("="*50)
    
    pdf_path = "data/1. Jan 31st 2022.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    # Step 1: Raw extraction
    print("📋 STEP 1: Raw extraction")
    extractor = BankStatementExtractor(pdf_path)
    raw_df = extractor.extract()
    
    if raw_df is not None and not raw_df.empty:
        print(f"✅ Raw extraction: {len(raw_df)} transactions")
        print(f"Columns: {list(raw_df.columns)}")
        
        # Check Holland Leasing
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
    
    # Step 2: Check the _clean_and_validate method
    print("\n📋 STEP 2: Check _clean_and_validate method")
    
    # Apply the same cleaning as the extractor
    df_clean = raw_df.copy()
    
    # Remove rows that are likely headers/footers
    df_clean = extractor._remove_headers_footers(df_clean)
    print(f"After removing headers/footers: {len(df_clean)}")
    
    # Clean Date column
    if 'Date' in df_clean.columns:
        df_clean['Date'] = df_clean['Date'].apply(extractor._parse_date)
        df_clean = df_clean[df_clean['Date'].notna()]
    print(f"After date cleaning: {len(df_clean)}")
    
    # Clean Description column
    if 'Description' in df_clean.columns:
        df_clean['Description'] = df_clean['Description'].astype(str).str.strip()
        df_clean = df_clean[df_clean['Description'] != '']
        df_clean = df_clean[df_clean['Description'] != 'None']
        df_clean = df_clean[~df_clean['Description'].str.lower().str.contains('beginning balance|ending balance|page total|continued', na=False)]
    print(f"After description cleaning: {len(df_clean)}")
    
    # Clean amount columns
    for col in ['Withdrawals', 'Deposits', 'Balance']:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(extractor._clean_amount)
    print(f"After amount cleaning: {len(df_clean)}")
    
    # Remove rows with no amounts
    if 'Withdrawals' in df_clean.columns and 'Deposits' in df_clean.columns:
        df_clean = df_clean[(df_clean['Withdrawals'].notna()) | (df_clean['Deposits'].notna())]
    print(f"After removing rows with no amounts: {len(df_clean)}")
    
    # Check Holland Leasing after cleaning
    holland_clean = df_clean[df_clean['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    jan21_holland_clean = holland_clean[holland_clean['Date'].astype(str).str.contains('2022-01-21', na=False)]
    
    print(f"\n🏢 Jan 21 Holland Leasing after cleaning: {len(jan21_holland_clean)}")
    if len(jan21_holland_clean) > 0:
        for i, (_, row) in enumerate(jan21_holland_clean.iterrows()):
            print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
            print(f"     Description: {row.get('Description', 'N/A')}")
            print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
            print(f"     Deposits: {row.get('Deposits', 'N/A')}")
            print(f"     Balance: {row.get('Balance', 'N/A')}")
            print()
    
    # Check for duplicates
    print(f"\n🔍 Checking for duplicates...")
    duplicate_subset = ['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance']
    duplicates = df_clean[df_clean.duplicated(subset=duplicate_subset, keep=False)]
    print(f"Duplicates found: {len(duplicates)}")
    
    if len(duplicates) > 0:
        print(f"\n📋 Duplicate transactions:")
        for i, (_, row) in enumerate(duplicates.head(5).iterrows()):
            print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
            print(f"     Description: {row.get('Description', 'N/A')}")
            print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
            print(f"     Deposits: {row.get('Deposits', 'N/A')}")
            print(f"     Balance: {row.get('Balance', 'N/A')}")
            print()

if __name__ == "__main__":
    debug_final_extraction()

