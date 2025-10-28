import camelot
import pandas as pd

# Debug Camelot extraction for the first table
pdf_path = 'data/Bank Statements/-1. January 2023.pdf'

print("=== CAMELOT DEBUG ===")
print(f"Extracting from: {pdf_path}")

# Extract all tables
tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')

print(f"\nFound {len(tables)} tables")

# Check Table 2 specifically (should be the first transaction table)
if len(tables) > 1:
    table = tables[1]  # Table 2
    print(f"\n=== TABLE 2 (First Transaction Table) ===")
    print(f"Shape: {table.df.shape}")
    print(f"Columns: {len(table.df.columns)}")
    
    print(f"\nFirst 20 rows:")
    print(table.df.head(20))
    
    print(f"\nColumn analysis:")
    for i, col in enumerate(table.df.columns):
        print(f"Column {i}: '{col}'")
    
    # Show sample transaction rows
    print(f"\nSample transaction rows:")
    for i, row in table.df.iterrows():
        if i > 20:  # Limit to first 20 rows
            break
        row_str = ' | '.join([str(cell) for cell in row])
        print(f"Row {i}: {row_str}")
else:
    print("No Table 2 found!")
