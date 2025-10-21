#!/usr/bin/env python3
"""
Debug all tables to see if Holland Leasing appears in multiple tables
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def debug_all_tables():
    print("🔍 DEBUGGING ALL TABLES FOR HOLLAND LEASING")
    print("="*60)
    
    pdf_path = "data/1. Jan 31st 2022.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    extractor = BankStatementExtractor(pdf_path)
    
    try:
        import camelot
        
        # Get all tables
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        
        all_holland_transactions = []
        
        # Check each table
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
                        all_holland_transactions.extend(holland_in_table.to_dict('records'))
                    else:
                        print(f"  🏢 Holland Leasing: 0")
        
        print(f"\n🏢 Total Holland Leasing transactions found: {len(all_holland_transactions)}")
        
        if len(all_holland_transactions) > 0:
            print(f"\n📋 All Holland Leasing transactions:")
            for i, trans in enumerate(all_holland_transactions):
                print(f"  {i+1}. Date: {trans.get('Date', 'N/A')}")
                print(f"     Description: {trans.get('Description', 'N/A')}")
                print(f"     Withdrawals: {trans.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {trans.get('Deposits', 'N/A')}")
                print(f"     Balance: {trans.get('Balance', 'N/A')}")
                print()
        
        # Check for Jan 21 specifically
        jan21_holland = [t for t in all_holland_transactions if '2022-01-21' in str(t.get('Date', ''))]
        print(f"\n📅 Jan 21 Holland Leasing transactions: {len(jan21_holland)}")
        
        if len(jan21_holland) > 0:
            print(f"\n📋 Jan 21 Holland Leasing transactions:")
            for i, trans in enumerate(jan21_holland):
                print(f"  {i+1}. Date: {trans.get('Date', 'N/A')}")
                print(f"     Description: {trans.get('Description', 'N/A')}")
                print(f"     Withdrawals: {trans.get('Withdrawals', 'N/A')}")
                print(f"     Deposits: {trans.get('Deposits', 'N/A')}")
                print(f"     Balance: {trans.get('Balance', 'N/A')}")
                print()
        
        # Now test the combination logic
        print(f"\n🔍 Testing combination logic...")
        
        # Convert to DataFrame
        all_df = pd.DataFrame(all_holland_transactions)
        print(f"Total transactions before combination: {len(all_df)}")
        
        # Apply the same deduplication as the extractor
        duplicate_subset = ['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance']
        combined_df = all_df.drop_duplicates(subset=duplicate_subset)
        print(f"After deduplication: {len(combined_df)}")
        print(f"Removed: {len(all_df) - len(combined_df)}")
        
        # Check Jan 21 after combination
        jan21_combined = combined_df[combined_df['Date'].astype(str).str.contains('2022-01-21', na=False)]
        print(f"\n📅 Jan 21 Holland Leasing after combination: {len(jan21_combined)}")
        
        if len(jan21_combined) > 0:
            print(f"\n📋 Jan 21 Holland Leasing after combination:")
            for i, (_, row) in enumerate(jan21_combined.iterrows()):
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
    debug_all_tables()

