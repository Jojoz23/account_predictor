import pandas as pd

df = pd.read_excel('extracted_1. January 2025 e-statement- bank.xlsx', sheet_name='Transactions')

print("="*70)
print("FINAL EXTRACTION RESULTS")
print("="*70)

print(f"\nExtracted: {len(df)} / 134 expected")
print(f"Missing: {134 - len(df)}")

print(f"\nBreakdown:")
withdrawals_count = df['Withdrawals'].notna().sum()
deposits_count = df['Deposits'].notna().sum()
print(f"  Withdrawals: {withdrawals_count} (expected 36, difference: {36 - withdrawals_count})")
print(f"  Deposits: {deposits_count} (expected 98, difference: {98 - deposits_count})")

print(f"\n=== Sample Transactions ===")
print(df[['Date', 'Description', 'Withdrawals', 'Deposits']].head(15).to_string(index=False))

# Check if there are still "DEPOSIT" rows
deposit_only = df[df['Description'] == 'DEPOSIT']
print(f"\n=== Rows with description exactly 'DEPOSIT': {len(deposit_only)} ===")
if len(deposit_only) > 0:
    print(deposit_only[['Date', 'Description', 'Deposits']].head(10).to_string(index=False))



