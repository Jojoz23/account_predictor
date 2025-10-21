import pdfplumber
import pandas as pd
import re

# Run full extraction
exec(open('extract_all_text_method.py').read())

print("\n" + "="*70)
print("ANALYZING DUPLICATES")
print("="*70)

print(f"\nBefore deduplication: {len(df)}")

# Find duplicates
duplicates = df[df.duplicated(keep=False)]
print(f"Duplicate rows (including originals): {len(duplicates)}")

if len(duplicates) > 0:
    print(f"\n=== ALL DUPLICATES ===")
    print(duplicates[['Date', 'Description', 'Withdrawals', 'Deposits']].to_string())
    
    # Show which rows are duplicated
    print(f"\n=== DUPLICATE GROUPS ===")
    for _, group in duplicates.groupby(['Date', 'Description', 'Withdrawals', 'Deposits']):
        if len(group) > 1:
            print(f"\nDuplicated {len(group)} times:")
            print(f"  Date: {group.iloc[0]['Date']}")
            print(f"  Description: {group.iloc[0]['Description']}")
            print(f"  Withdrawal: {group.iloc[0]['Withdrawals']}")
            print(f"  Deposit: {group.iloc[0]['Deposits']}")

# After removing duplicates
df_unique = df.drop_duplicates()
print(f"\n\nAfter removing duplicates: {len(df_unique)}")
print(f"Removed: {len(df) - len(df_unique)}")

# But are these REAL duplicates or are they different transactions on the same day?
print(f"\n=== ARE THESE REALLY DUPLICATES? ===")
print("Checking if there are multiple legitimate transactions with same date/description...")

same_day_same_desc = df.groupby(['Date', 'Description']).size()
multiple_same = same_day_same_desc[same_day_same_desc > 1]
if len(multiple_same) > 0:
    print(f"\nFound {len(multiple_same)} description patterns that appear multiple times:")
    print(multiple_same.head(10))



