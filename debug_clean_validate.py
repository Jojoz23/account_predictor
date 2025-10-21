#!/usr/bin/env python3
"""
Debug the _clean_and_validate method step by step
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def debug_clean_validate():
    print("🔍 DEBUGGING _clean_and_validate METHOD")
    print("="*50)
    
    pdf_path = "data/1. Jan 31st 2022.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    # Get the raw extraction first
    extractor = BankStatementExtractor(pdf_path)
    raw_df = extractor.extract()
    
    if raw_df is None or raw_df.empty:
        print("❌ Raw extraction failed")
        return
    
    print(f"📊 Starting with {len(raw_df)} transactions")
    
    # Check Holland Leasing before any cleaning
    holland_before = raw_df[raw_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    jan21_before = holland_before[holland_before['Date'].astype(str).str.contains('2022-01-21', na=False)]
    print(f"\n🏢 Jan 21 Holland Leasing BEFORE cleaning: {len(jan21_before)}")
    
    if len(jan21_before) > 0:
        for i, (_, row) in enumerate(jan21_before.iterrows()):
            print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
            print(f"     Description: {row.get('Description', 'N/A')}")
            print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
            print(f"     Deposits: {row.get('Deposits', 'N/A')}")
            print(f"     Balance: {row.get('Balance', 'N/A')}")
            print()
    
    # Step 1: Remove headers/footers
    print(f"\n📋 STEP 1: Remove headers/footers")
    df_step1 = extractor._remove_headers_footers(raw_df)
    print(f"After removing headers/footers: {len(df_step1)}")
    
    holland_step1 = df_step1[df_step1['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    jan21_step1 = holland_step1[holland_step1['Date'].astype(str).str.contains('2022-01-21', na=False)]
    print(f"Jan 21 Holland Leasing after step 1: {len(jan21_step1)}")
    
    # Step 2: Clean Date column
    print(f"\n📋 STEP 2: Clean Date column")
    df_step2 = df_step1.copy()
    if 'Date' in df_step2.columns:
        df_step2['Date'] = df_step2['Date'].apply(extractor._parse_date)
        df_step2 = df_step2[df_step2['Date'].notna()]
    print(f"After date cleaning: {len(df_step2)}")
    
    holland_step2 = df_step2[df_step2['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    jan21_step2 = holland_step2[holland_step2['Date'].astype(str).str.contains('2022-01-21', na=False)]
    print(f"Jan 21 Holland Leasing after step 2: {len(jan21_step2)}")
    
    # Step 3: Clean Description column
    print(f"\n📋 STEP 3: Clean Description column")
    df_step3 = df_step2.copy()
    if 'Description' in df_step3.columns:
        df_step3['Description'] = df_step3['Description'].astype(str).str.strip()
        df_step3 = df_step3[df_step3['Description'] != '']
        df_step3 = df_step3[df_step3['Description'] != 'None']
        df_step3 = df_step3[~df_step3['Description'].str.lower().str.contains('beginning balance|ending balance|page total|continued', na=False)]
    print(f"After description cleaning: {len(df_step3)}")
    
    holland_step3 = df_step3[df_step3['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    jan21_step3 = holland_step3[holland_step3['Date'].astype(str).str.contains('2022-01-21', na=False)]
    print(f"Jan 21 Holland Leasing after step 3: {len(jan21_step3)}")
    
    # Step 4: Clean amount columns
    print(f"\n📋 STEP 4: Clean amount columns")
    df_step4 = df_step3.copy()
    for col in ['Withdrawals', 'Deposits', 'Balance']:
        if col in df_step4.columns:
            df_step4[col] = df_step4[col].apply(extractor._clean_amount)
    print(f"After amount cleaning: {len(df_step4)}")
    
    holland_step4 = df_step4[df_step4['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    jan21_step4 = holland_step4[holland_step4['Date'].astype(str).str.contains('2022-01-21', na=False)]
    print(f"Jan 21 Holland Leasing after step 4: {len(jan21_step4)}")
    
    # Step 5: Remove rows with no amounts
    print(f"\n📋 STEP 5: Remove rows with no amounts")
    df_step5 = df_step4.copy()
    if 'Withdrawals' in df_step5.columns and 'Deposits' in df_step5.columns:
        df_step5 = df_step5[(df_step5['Withdrawals'].notna()) | (df_step5['Deposits'].notna())]
    print(f"After removing rows with no amounts: {len(df_step5)}")
    
    holland_step5 = df_step5[df_step5['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    jan21_step5 = holland_step5[holland_step5['Date'].astype(str).str.contains('2022-01-21', na=False)]
    print(f"Jan 21 Holland Leasing after step 5: {len(jan21_step5)}")
    
    # Step 6: Remove duplicates
    print(f"\n📋 STEP 6: Remove duplicates")
    df_step6 = df_step5.copy()
    
    duplicate_subset = ['Date', 'Description']
    if 'Withdrawals' in df_step6.columns:
        duplicate_subset.append('Withdrawals')
    if 'Deposits' in df_step6.columns:
        duplicate_subset.append('Deposits')
    if 'Balance' in df_step6.columns:
        duplicate_subset.append('Balance')
    
    print(f"Deduplication subset: {duplicate_subset}")
    
    before_dedup = len(df_step6)
    df_deduped = df_step6.drop_duplicates(subset=duplicate_subset)
    removed_by_dedup = before_dedup - len(df_deduped)
    
    print(f"Before deduplication: {before_dedup}")
    print(f"After deduplication: {len(df_deduped)}")
    print(f"Removed by deduplication: {removed_by_dedup}")
    
    # Check if safeguard is triggered
    if removed_by_dedup > 5:
        print(f"⚠️  Safeguard triggered - keeping original DataFrame")
        df_final = df_step6
    else:
        print(f"✅ Safeguard not triggered - using deduplicated DataFrame")
        df_final = df_deduped
    
    holland_final = df_final[df_final['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    jan21_final = holland_final[holland_final['Date'].astype(str).str.contains('2022-01-21', na=False)]
    print(f"Jan 21 Holland Leasing after step 6: {len(jan21_final)}")
    
    if len(jan21_final) > 0:
        print(f"\n📋 Final Jan 21 Holland Leasing transactions:")
        for i, (_, row) in enumerate(jan21_final.iterrows()):
            print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
            print(f"     Description: {row.get('Description', 'N/A')}")
            print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
            print(f"     Deposits: {row.get('Deposits', 'N/A')}")
            print(f"     Balance: {row.get('Balance', 'N/A')}")
            print()

if __name__ == "__main__":
    debug_clean_validate()

