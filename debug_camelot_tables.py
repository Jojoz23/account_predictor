#!/usr/bin/env python3
"""
Debug individual Camelot tables to find both Holland Leasing transactions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_bank_statements import BankStatementExtractor
import pandas as pd

def debug_camelot_tables():
    print("🔍 DEBUGGING INDIVIDUAL CAMELOT TABLES")
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
        print(f"Camelot found {len(tables_stream)} tables")
        
        all_holland_transactions = []
        
        # Check each table individually
        for i, table in enumerate(tables_stream):
            df = table.df
            print(f"\n📋 Table {i+1}:")
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {list(df.columns)}")
            
            # Check if it's a transaction table
            is_transaction = extractor._is_transaction_table(df)
            print(f"  Is transaction table: {is_transaction}")
            
            if is_transaction:
                # Parse transactions from this table
                transactions = extractor._parse_camelot_transactions(df)
                print(f"  Extracted {len(transactions)} transactions")
                
                if len(transactions) > 0:
                    # Check for Holland Leasing in this table
                    holland_in_table = transactions[transactions['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
                    print(f"  Holland Leasing in this table: {len(holland_in_table)}")
                    
                    if len(holland_in_table) > 0:
                        print(f"  📋 Holland Leasing transactions in Table {i+1}:")
                        for j, (_, row) in enumerate(holland_in_table.iterrows()):
                            print(f"    {j+1}. Date: {row.get('Date', 'N/A')}")
                            print(f"       Description: {row.get('Description', 'N/A')}")
                            print(f"       Withdrawals: {row.get('Withdrawals', 'N/A')}")
                            print(f"       Deposits: {row.get('Deposits', 'N/A')}")
                            print(f"       Balance: {row.get('Balance', 'N/A')}")
                            print()
                        
                        # Add to our collection
                        all_holland_transactions.extend(holland_in_table.to_dict('records'))
        
        print(f"\n🏢 Total Holland Leasing transactions found across all tables: {len(all_holland_transactions)}")
        
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
    
    except ImportError:
        print("❌ Camelot not installed")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    debug_camelot_tables()

