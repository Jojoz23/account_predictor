#!/usr/bin/env python3
"""
Debug the deduplication data types to see why one transaction is being removed
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def debug_deduplication_data_types():
    print("🔍 DEBUGGING DEDUPLICATION DATA TYPES")
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
        
        print(f"📊 Total transactions before deduplication: {len(all_camelot_transactions)}")
        
        # Convert to DataFrame
        camelot_df = pd.DataFrame(all_camelot_transactions)
        print(f"DataFrame shape: {camelot_df.shape}")
        print(f"Columns: {list(camelot_df.columns)}")
        
        # Check Holland Leasing before deduplication
        holland_before = camelot_df[camelot_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        jan21_before = holland_before[holland_before['Date'].astype(str).str.contains('2022-01-21', na=False)]
        
        print(f"\n🏢 Jan 21 Holland Leasing BEFORE deduplication: {len(jan21_before)}")
        if len(jan21_before) > 0:
            for i, (_, row) in enumerate(jan21_before.iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Description: {row.get('Description', 'N/A')}")
                print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {row.get('Deposits', 'N/A')}")
                print(f"     Balance: {row.get('Balance', 'N/A')}")
                print()
        
        # Check data types
        print(f"\n🔍 Checking data types...")
        print(f"Date dtype: {camelot_df['Date'].dtype}")
        print(f"Description dtype: {camelot_df['Description'].dtype}")
        print(f"Withdrawals dtype: {camelot_df['Withdrawals'].dtype}")
        print(f"Deposits dtype: {camelot_df['Deposits'].dtype}")
        print(f"Balance dtype: {camelot_df['Balance'].dtype}")
        
        # Check for any data issues
        print(f"\n🔍 Checking for data issues...")
        
        # Check for NaN values
        nan_counts = camelot_df.isnull().sum()
        print(f"NaN counts per column:")
        for col, count in nan_counts.items():
            if count > 0:
                print(f"  {col}: {count}")
        
        # Check for empty strings
        empty_counts = (camelot_df == '').sum()
        print(f"Empty string counts per column:")
        for col, count in empty_counts.items():
            if count > 0:
                print(f"  {col}: {count}")
        
        # Check for None values
        none_counts = (camelot_df == 'None').sum()
        print(f"None string counts per column:")
        for col, count in none_counts.items():
            if count > 0:
                print(f"  {col}: {count}")
        
        # Now apply deduplication
        print(f"\n🔍 Applying deduplication...")
        duplicate_subset = ['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance']
        camelot_df_dedup = camelot_df.drop_duplicates(subset=duplicate_subset)
        
        print(f"Before deduplication: {len(camelot_df)}")
        print(f"After deduplication: {len(camelot_df_dedup)}")
        print(f"Removed: {len(camelot_df) - len(camelot_df_dedup)}")
        
        # Check Holland Leasing after deduplication
        holland_after = camelot_df_dedup[camelot_df_dedup['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        jan21_after = holland_after[holland_after['Date'].astype(str).str.contains('2022-01-21', na=False)]
        
        print(f"\n🏢 Jan 21 Holland Leasing AFTER deduplication: {len(jan21_after)}")
        if len(jan21_after) > 0:
            for i, (_, row) in enumerate(jan21_after.iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Description: {row.get('Description', 'N/A')}")
                print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {row.get('Deposits', 'N/A')}")
                print(f"     Balance: {row.get('Balance', 'N/A')}")
                print()
        
        # Check for exact duplicates
        print(f"\n🔍 Checking for exact duplicates...")
        exact_duplicates = camelot_df[camelot_df.duplicated(subset=duplicate_subset, keep=False)]
        print(f"Exact duplicates found: {len(exact_duplicates)}")
        
        if len(exact_duplicates) > 0:
            print(f"\n📋 Exact duplicates:")
            for i, (_, row) in enumerate(exact_duplicates.head(5).iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Description: {row.get('Description', 'N/A')}")
                print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {row.get('Deposits', 'N/A')}")
                print(f"     Balance: {row.get('Balance', 'N/A')}")
                print()
    
    except ImportError:
        print("❌ Camelot not installed")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    debug_deduplication_data_types()

