import pdfplumber
import pandas as pd

pdf_path = "data/1. January 2025 e-statement- bank.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page2 = pdf.pages[1]
    tables = page2.extract_tables()
    
    print("="*70)
    print("TABLE COLUMN STRUCTURE")
    print("="*70)
    
    # Check first table
    table = tables[0]
    print(f"\nTable 1: {len(table)} rows, {len(table[0])} columns")
    print(f"\nRaw table data:")
    for i, row in enumerate(table):
        print(f"Row {i}: {row}")
    
    # Now check how it's converted to DataFrame
    print(f"\n" + "="*70)
    print("WHEN CONVERTED TO DATAFRAME (assuming 5-column format)")
    print("="*70)
    
    df = pd.DataFrame([table[0]], columns=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'])
    print(df.to_string())
    
    # Check another table (a deposit)
    print(f"\n" + "="*70)
    print("CHECKING A DEPOSIT TRANSACTION")
    print("="*70)
    
    # Find a DEPOSIT transaction
    for i, table in enumerate(tables):
        if table and len(table) > 0:
            desc = str(table[0][1]) if len(table[0]) > 1 else ''
            if 'DEPOSIT' in desc:
                print(f"\nTable {i+1} (DEPOSIT):")
                print(f"Raw: {table[0]}")
                df_deposit = pd.DataFrame([table[0]], columns=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'])
                print(df_deposit.to_string())
                break


