import pdfplumber
import pandas as pd
import re
from extract_bank_statements import BankStatementExtractor

pdf_path = "data/1. January 2025 e-statement- bank.pdf"

# Run my custom text extraction
exec(open('extract_all_text_method.py').read())

print("\n" + "="*70)
print("ANALYZING CLEANING PROCESS")
print("="*70)

extractor = BankStatementExtractor(pdf_path)

# The df from extract_all_text_method.py is still in scope
print(f"\nBefore cleaning: {len(df)} transactions")

# Apply header/footer removal
df_no_headers = extractor._remove_headers_footers(df.copy())
print(f"After header/footer removal: {len(df_no_headers)} (removed {len(df) - len(df_no_headers)})")

# Date cleaning
df_dates = df_no_headers.copy()
df_dates['Date'] = df_dates['Date'].apply(extractor._parse_date)
df_dates_clean = df_dates[df_dates['Date'].notna()]
print(f"After date parsing: {len(df_dates_clean)} (removed {len(df_no_headers) - len(df_dates_clean)})")

# Description cleaning
df_desc = df_dates_clean.copy()
df_desc['Description'] = df_desc['Description'].astype(str).str.strip()
df_desc = df_desc[df_desc['Description'] != '']
df_desc = df_desc[df_desc['Description'] != 'None']
df_desc = df_desc[~df_desc['Description'].str.lower().str.contains('beginning balance|ending balance|page total|continued', na=False)]
print(f"After description cleaning: {len(df_desc)} (removed {len(df_dates_clean) - len(df_desc)})")

# Amount cleaning and filtering
df_amounts = df_desc.copy()
for col in ['Withdrawals', 'Deposits', 'Balance']:
    if col in df_amounts.columns:
        df_amounts[col] = df_amounts[col].apply(extractor._clean_amount)

before_filter = len(df_amounts)
df_filtered = df_amounts[(df_amounts['Withdrawals'].notna()) | (df_amounts['Deposits'].notna())]
print(f"After removing rows with no amounts: {len(df_filtered)} (removed {before_filter - len(df_filtered)})")

if before_filter - len(df_filtered) > 0:
    removed = df_amounts[~df_amounts.index.isin(df_filtered.index)]
    print(f"\n⚠️ Rows removed (no amounts):")
    print(removed[['Date', 'Description', 'Withdrawals', 'Deposits']].head(15).to_string())

# Duplicates
df_final = df_filtered.drop_duplicates()
print(f"\nAfter removing duplicates: {len(df_final)} (removed {len(df_filtered) - len(df_final)})")

print(f"\n=== FINAL RESULT ===")
print(f"Extracted: {len(df_final)} / 134 expected")
print(f"Withdrawals: {df_final['Withdrawals'].notna().sum()}")
print(f"Deposits: {df_final['Deposits'].notna().sum()}")



