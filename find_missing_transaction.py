#!/usr/bin/env python3
"""
Find which transaction is being removed during cleaning
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def find_missing_transaction():
    print("🔍 FINDING MISSING TRANSACTION")
    print("="*50)
    
    pdf_path = "data/1. Jan 31st 2022.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    extractor = BankStatementExtractor(pdf_path)
    
    try:
        import camelot
        
        # Get all tables
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        
        all_camelot_transactions = []
        
        # Extract from each table individually
        for i, table in enumerate(tables_stream):
            df = table.df
            is_transaction = extractor._is_transaction_table(df)
            
            if is_transaction:
                transactions = extractor._parse_camelot_transactions(df)
                if len(transactions) > 0:
                    all_camelot_transactions.extend(transactions.to_dict('records'))
        
        # Apply deduplication
        camelot_df = pd.DataFrame(all_camelot_transactions)
        camelot_df = camelot_df.drop_duplicates(subset=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'])
        
        print(f"📊 After Camelot deduplication: {len(camelot_df)} transactions")
        
        # Check Holland Leasing before cleaning
        holland_before = camelot_df[camelot_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
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
        
        # Now apply cleaning
        print(f"\n🧹 Applying _clean_and_validate...")
        cleaned_df = extractor._clean_and_validate(camelot_df)
        
        if cleaned_df is not None and not cleaned_df.empty:
            print(f"After cleaning: {len(cleaned_df)} transactions")
            
            # Check Holland Leasing after cleaning
            holland_after = cleaned_df[cleaned_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
            jan21_after = holland_after[holland_after['Date'].astype(str).str.contains('2022-01-21', na=False)]
            
            print(f"\n🏢 Jan 21 Holland Leasing AFTER cleaning: {len(jan21_after)}")
            if len(jan21_after) > 0:
                for i, (_, row) in enumerate(jan21_after.iterrows()):
                    print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                    print(f"     Description: {row.get('Description', 'N/A')}")
                    print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
                    print(f"     Deposits: {row.get('Deposits', 'N/A')}")
                    print(f"     Balance: {row.get('Balance', 'N/A')}")
                    print()
            
            # Find which transaction was removed
            print(f"\n🔍 Finding removed transaction...")
            
            # Get indices before and after
            before_indices = set(camelot_df.index)
            after_indices = set(cleaned_df.index)
            
            removed_indices = before_indices - after_indices
            print(f"Removed {len(removed_indices)} transaction(s)")
            
            if len(removed_indices) > 0:
                print(f"\n📋 Removed transaction(s):")
                for idx in removed_indices:
                    row = camelot_df.loc[idx]
                    print(f"  Index: {idx}")
                    print(f"  Date: {row.get('Date', 'N/A')}")
                    print(f"  Description: {row.get('Description', 'N/A')}")
                    print(f"  Withdrawals: {row.get('Withdrawals', 'N/A')}")
                    print(f"  Deposits: {row.get('Deposits', 'N/A')}")
                    print(f"  Balance: {row.get('Balance', 'N/A')}")
                    print()
    
    except ImportError:
        print("❌ Camelot not installed")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_missing_transaction()


