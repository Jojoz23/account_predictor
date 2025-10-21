import pdfplumber
import pandas as pd

pdf_path = "data/1. January 2025 e-statement- bank.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print("="*70)
    print("SEARCHING FOR MULTI-ROW TRANSACTION TABLES")
    print("="*70)
    
    total_single_row = 0
    total_multi_row = 0
    
    for page_num, page in enumerate(pdf.pages, 1):
        tables = page.extract_tables()
        
        multi_row_tables = [t for t in tables if len(t) > 1]
        single_row_tables = [t for t in tables if len(t) == 1]
        
        if multi_row_tables:
            print(f"\n📋 PAGE {page_num}: Found {len(multi_row_tables)} MULTI-ROW tables")
            for i, table in enumerate(multi_row_tables):
                print(f"  Table {i+1}: {len(table)} rows x {len(table[0]) if table else 0} cols")
                # Show first few rows
                df = pd.DataFrame(table)
                print(df.head().to_string())
                print()
        
        total_single_row += len(single_row_tables)
        total_multi_row += len(multi_row_tables)
    
    print(f"\n" + "="*70)
    print(f"Summary:")
    print(f"  Single-row tables: {total_single_row}")
    print(f"  Multi-row tables: {total_multi_row}")
    print(f"  Total tables: {total_single_row + total_multi_row}")
    print(f"  Expected transactions: 134")



