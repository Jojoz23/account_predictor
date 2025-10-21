import pdfplumber
import pandas as pd

pdf_path = "data/1. January 2025 e-statement- bank.pdf"

with pdfplumber.open(pdf_path) as pdf:
    all_tables = []
    
    # Collect all single-row tables from all pages
    for page_num, page in enumerate(pdf.pages, 1):
        tables = page.extract_tables()
        for table in tables:
            if len(table) == 1 and len(table[0]) == 5:
                all_tables.append(table[0])
    
    print(f"Total single-row 5-column tables: {len(all_tables)}")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_tables, columns=['Date', 'Description', 'Col3', 'Col4', 'Balance'])
    
    # Clean multi-line descriptions
    df['Description'] = df['Description'].str.replace('\n', ' ').str.replace('  ', ' ').str.strip()
    
    # Check which column has the amount
    print(f"\nChecking column usage:")
    col3_has_value = df['Col3'].notna() & (df['Col3'] != '')
    col4_has_value = df['Col4'].notna() & (df['Col4'] != '')
    
    print(f"  Col3 has values: {col3_has_value.sum()} rows")
    print(f"  Col4 has values: {col4_has_value.sum()} rows")
    print(f"  Both have values: {(col3_has_value & col4_has_value).sum()} rows")
    print(f"  Neither has values: {(~col3_has_value & ~col4_has_value).sum()} rows")
    
    # Show examples
    print(f"\n=== Examples where Col3 has value (Withdrawals) ===")
    print(df[col3_has_value][['Date', 'Description', 'Col3', 'Col4']].head(5).to_string(index=False))
    
    print(f"\n=== Examples where Col4 has value (Deposits) ===")
    print(df[col4_has_value][['Date', 'Description', 'Col3', 'Col4']].head(5).to_string(index=False))
    
    # Assign correctly
    df['Withdrawals'] = df['Col3'].where(col3_has_value, None)
    df['Deposits'] = df['Col4'].where(col4_has_value, None)
    
    # Count
    withdrawals_count = df['Withdrawals'].notna().sum()
    deposits_count = df['Deposits'].notna().sum()
    
    print(f"\n=== FINAL COUNT ===")
    print(f"Withdrawals: {withdrawals_count}")
    print(f"Deposits: {deposits_count}")
    print(f"Total: {len(df)}")
    print(f"\nExpected: 36 debits + 98 credits = 134")
    print(f"Missing: {134 - len(df)} transactions")



