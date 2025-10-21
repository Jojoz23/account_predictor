#!/usr/bin/env python3
"""
Debug the Camelot combination logic to see where one transaction is lost
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def debug_camelot_combination():
    print("🔍 DEBUGGING CAMELOT COMBINATION LOGIC")
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
                print(f"\n📋 Table {i+1}:")
                transactions = extractor._parse_camelot_transactions(df)
                
                if len(transactions) > 0:
                    # Check for Holland Leasing in this table
                    holland_in_table = transactions[transactions['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
                    
                    if len(holland_in_table) > 0:
                        print(f"  🏢 Holland Leasing found: {len(holland_in_table)}")
                        for j, (_, row) in enumerate(holland_in_table.iterrows()):
                            print(f"    {j+1}. Date: {row.get('Date', 'N/A')}")
                            print(f"       Description: {row.get('Description', 'N/A')}")
                            print(f"       Withdrawals: {row.get('Withdrawals', 'N/A')}")
                            print(f"       Deposits: {row.get('Deposits', 'N/A')}")
                            print(f"       Balance: {row.get('Balance', 'N/A')}")
                            print()
                    
                    # Add to our collection
                    all_camelot_transactions.extend(transactions.to_dict('records'))
                    print(f"  Total transactions from this table: {len(transactions)}")
                    print(f"  Cumulative total: {len(all_camelot_transactions)}")
        
        print(f"\n📊 Total transactions before combination: {len(all_camelot_transactions)}")
        
        # Check Holland Leasing before combination
        holland_before = [t for t in all_camelot_transactions if 'HOLAND LEASING' in str(t.get('Description', ''))]
        jan21_before = [t for t in holland_before if '2022-01-21' in str(t.get('Date', ''))]
        
        print(f"\n🏢 Jan 21 Holland Leasing BEFORE combination: {len(jan21_before)}")
        if len(jan21_before) > 0:
            for i, trans in enumerate(jan21_before):
                print(f"  {i+1}. Date: {trans.get('Date', 'N/A')}")
                print(f"     Description: {trans.get('Description', 'N/A')}")
                print(f"     Withdrawals: {trans.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {trans.get('Deposits', 'N/A')}")
                print(f"     Balance: {trans.get('Balance', 'N/A')}")
                print()
        
        # Now apply the same combination logic as the extractor
        print(f"\n🔍 Applying combination logic...")
        
        # Convert to DataFrame
        camelot_df = pd.DataFrame(all_camelot_transactions)
        print(f"DataFrame shape: {camelot_df.shape}")
        print(f"Columns: {list(camelot_df.columns)}")
        
        # Apply deduplication
        duplicate_subset = ['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance']
        camelot_df_dedup = camelot_df.drop_duplicates(subset=duplicate_subset)
        
        print(f"After deduplication: {len(camelot_df_dedup)}")
        print(f"Removed: {len(camelot_df) - len(camelot_df_dedup)}")
        
        # Check Holland Leasing after combination
        holland_after = camelot_df_dedup[camelot_df_dedup['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
        jan21_after = holland_after[holland_after['Date'].astype(str).str.contains('2022-01-21', na=False)]
        
        print(f"\n🏢 Jan 21 Holland Leasing AFTER combination: {len(jan21_after)}")
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
    debug_camelot_combination()

