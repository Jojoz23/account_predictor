from extract_bank_statements import extract_from_pdf
import pandas as pd

# Test the March statement specifically
print('Testing March 2023 statement...')
result = extract_from_pdf('data/Bank Statements/0. March 2023.pdf', save_excel=False)

if result is not None:
    print(f'March statement extracted {len(result)} transactions')
    
    # Check for any transactions on March 20, 2023
    march_20 = result[result['Date'].dt.strftime('%Y-%m-%d') == '2023-03-20']
    print(f'Transactions on March 20, 2023: {len(march_20)}')
    
    if len(march_20) > 0:
        print('March 20 transactions:')
        for idx, row in march_20.iterrows():
            desc = row['Description'][:50] + '...' if len(row['Description']) > 50 else row['Description']
            print(f'  {desc} - W: {row["Withdrawals"]}, D: {row["Deposits"]}')
    
    # Check date range
    print(f'Date range: {result["Date"].min()} to {result["Date"].max()}')
    
    # Check for any 2025 dates (incorrect year)
    wrong_year = result[result['Date'].dt.year == 2025]
    if len(wrong_year) > 0:
        print(f'WARNING: Found {len(wrong_year)} transactions with 2025 dates!')
        print('Sample 2025 dates:')
        print(wrong_year[['Date', 'Description']].head())
    
    # Check for duplicate transactions
    duplicates = result.duplicated(subset=['Date', 'Description', 'Withdrawals', 'Deposits'])
    if duplicates.any():
        print(f'WARNING: Found {duplicates.sum()} duplicate transactions!')
        print('Sample duplicates:')
        dup_rows = result[duplicates]
        print(dup_rows[['Date', 'Description', 'Withdrawals', 'Deposits']].head())
else:
    print('March statement extraction failed')
