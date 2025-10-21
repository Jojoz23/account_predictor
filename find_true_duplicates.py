import pdfplumber
import pandas as pd
import re
from extract_bank_statements import BankStatementExtractor

# Run extraction
exec(open('extract_all_text_method.py').read())

print("\n" + "="*70)
print("FINDING TRUE DUPLICATES")
print("="*70)

print(f"\nTotal extracted: {len(df)}")

# Apply the same cleaning as the extractor
extractor = BankStatementExtractor("data/1. January 2025 e-statement- bank.pdf")

# Clean amounts
for col in ['Withdrawals', 'Deposits', 'Balance']:
    if col in df.columns:
        df[col] = df[col].apply(extractor._clean_amount)

print(f"After amount cleaning: {len(df)}")

# Find duplicates using the same logic as extractor
duplicate_subset = ['Date', 'Description', 'Withdrawals', 'Deposits']

# Show duplicates
duplicates = df[df.duplicated(subset=duplicate_subset, keep=False)]
print(f"\nDuplicates (same date, description, AND amounts): {len(duplicates)}")

if len(duplicates) > 0:
    print(f"\n=== DUPLICATE TRANSACTIONS ===")
    print(duplicates[['Date', 'Description', 'Withdrawals', 'Deposits']].sort_values(['Date', 'Description']).to_string())

# Remove duplicates
df_unique = df.drop_duplicates(subset=duplicate_subset)
print(f"\nAfter deduplication: {len(df_unique)}")
print(f"Removed: {len(df) - len(df_unique)}")

#Check specific case: multiple $200 deposits on 01/06
deposits_200 = df[(df['Date'] == '01/06/2025') & (df['Description'] == 'DEPOSIT')]
print(f"\n=== 01/06/2025 DEPOSIT transactions ===")
print(deposits_200[['Date', 'Description', 'Deposits']].to_string())
print(f"Total: {len(deposits_200)}")



