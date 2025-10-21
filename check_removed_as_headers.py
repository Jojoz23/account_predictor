import pdfplumber
import pandas as pd
import re
from extract_bank_statements import BankStatementExtractor

# Run extraction
exec(open('extract_all_text_method.py').read())

extractor = BankStatementExtractor("data/1. January 2025 e-statement- bank.pdf")

print("\n" + "="*70)
print("TRANSACTIONS REMOVED AS HEADERS/FOOTERS")
print("="*70)

# Apply header/footer removal
df_no_headers = extractor._remove_headers_footers(df.copy())

# Find what was removed
removed_indices = df.index.difference(df_no_headers.index)
removed_df = df.loc[removed_indices]

print(f"\nTotal removed: {len(removed_df)}")
print(f"\nRemoved transactions:")
print(removed_df[['Date', 'Description', 'Withdrawals', 'Deposits']].to_string())

# Check which keyword triggered removal
print(f"\n\n=== ANALYZING WHY THEY WERE REMOVED ===")
exclude_keywords = [
    'beginning balance', 'ending balance', 'opening balance', 'closing balance',
    'page total', 'subtotal', 'total deposits', 'total withdrawals',
    'continued on next page', 'continued from previous',
    'daily balance', 'account summary',
    'date', 'description', 'withdrawal', 'deposit', 'balance'
]

for idx, row in removed_df.iterrows():
    desc = str(row['Description']).lower()
    matching_keywords = [kw for kw in exclude_keywords if kw in desc]
    print(f"\nRow {idx}: {row['Description'][:60]}")
    print(f"  Matched keywords: {matching_keywords}")



