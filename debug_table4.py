#!/usr/bin/env python3
"""
Debug Table 4 specifically to see why one Holland Leasing transaction is lost
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def debug_table4():
    print("🔍 DEBUGGING TABLE 4 SPECIFICALLY")
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
        
        # Focus on Table 4 (index 3)
        table4 = tables_stream[3]
        df4 = table4.df
        
        print(f"📋 Table 4 (index 3):")
        print(f"  Shape: {df4.shape}")
        print(f"  Columns: {list(df4.columns)}")
        
        # Show the raw table data
        print(f"\n📋 Raw Table 4 data:")
        print(df4.to_string())
        
        # Check if it's a transaction table
        is_transaction = extractor._is_transaction_table(df4)
        print(f"\nIs transaction table: {is_transaction}")
        
        if is_transaction:
            # Parse transactions from this table
            print(f"\n🔍 Parsing transactions from Table 4...")
            transactions = extractor._parse_camelot_transactions(df4)
            print(f"Extracted {len(transactions)} transactions")
            
            if len(transactions) > 0:
                print(f"\n📋 All transactions from Table 4:")
                for i, (_, row) in enumerate(transactions.iterrows()):
                    print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
                    print(f"     Description: {row.get('Description', 'N/A')}")
                    print(f"     Withdrawals: {row.get('Withdrawals', 'N/A')}")
                    print(f"     Deposits: {row.get('Deposits', 'N/A')}")
                    print(f"     Balance: {row.get('Balance', 'N/A')}")
                    print()
                
                # Check for Holland Leasing specifically
                holland = transactions[transactions['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
                print(f"\n🏢 Holland Leasing in Table 4: {len(holland)}")
                
                if len(holland) > 0:
                    print(f"\n📋 Holland Leasing transactions:")
                    for i, (_, row) in enumerate(holland.iterrows()):
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
    debug_table4()

