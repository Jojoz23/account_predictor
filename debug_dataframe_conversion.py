#!/usr/bin/env python3
"""
Debug the DataFrame conversion to see if one transaction is lost
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def debug_dataframe_conversion():
    print("🔍 DEBUGGING DATAFRAME CONVERSION")
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
        
        print(f"📊 Total transactions before DataFrame conversion: {len(all_camelot_transactions)}")
        
        # Check Holland Leasing before conversion
        holland_before = [t for t in all_camelot_transactions if 'HOLAND LEASING' in str(t.get('Description', ''))]
        jan21_before = [t for t in holland_before if '2022-01-21' in str(t.get('Date', ''))]
        
        print(f"\n🏢 Jan 21 Holland Leasing BEFORE DataFrame conversion: {len(jan21_before)}")
        if len(jan21_before) > 0:
            for i, trans in enumerate(jan21_before):
                print(f"  {i+1}. Date: {trans.get('Date', 'N/A')}")
                print(f"     Description: {trans.get('Description', 'N/A')}")
                print(f"     Withdrawals: {trans.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {trans.get('Deposits', 'N/A')}")
                print(f"     Balance: {trans.get('Balance', 'N/A')}")
                print()
        
        # Convert to DataFrame
        print(f"\n🔍 Converting to DataFrame...")
        camelot_df = pd.DataFrame(all_camelot_transactions)
        print(f"DataFrame shape: {camelot_df.shape}")
        print(f"Columns: {list(camelot_df.columns)}")
        
        # Check Holland Leasing after conversion
        holland_after = camelot_df[camelot_df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        jan21_after = holland_after[holland_after['Date'].astype(str).str.contains('2022-01-21', na=False)]
        
        print(f"\n🏢 Jan 21 Holland Leasing AFTER DataFrame conversion: {len(jan21_after)}")
        if len(jan21_after) > 0:
            for i, (_, row) in enumerate(jan21_after.iterrows()):
                print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                print(f"     Description: {row.get('Description', 'N/A')}")
                print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {row.get('Deposits', 'N/A')}")
                print(f"     Balance: {row.get('Balance', 'N/A')}")
                print()
        
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
    
    except ImportError:
        print("❌ Camelot not installed")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    debug_dataframe_conversion()

