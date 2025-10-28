from extract_bank_statements import extract_from_pdf
import pandas as pd

# Test the header-based extraction
print('Testing header-based extraction...')
result = extract_from_pdf('data/Bank Statements/-1. January 2023.pdf')

if result is not None:
    # Check overall balance
    total_withdrawals = result['Withdrawals'].sum()
    total_deposits = result['Deposits'].sum()
    net_change = total_deposits - total_withdrawals

    print(f'Balance check:')
    print(f'Total Withdrawals: {total_withdrawals:.2f}')
    print(f'Total Deposits: {total_deposits:.2f}')
    print(f'Net change: {net_change:.2f}')
    print(f'Expected net change: 270.48')
    print(f'Difference from expected: {abs(net_change - 270.48):.2f}')
    
    # Check specific problematic transactions
    api_alarm = result[result['Description'].str.contains('API ALARM', case=False, na=False)]
    db_fee = result[result['Description'].str.contains('DB FEE', case=False, na=False)]
    
    print(f'\nProblematic transactions:')
    if not api_alarm.empty:
        print(f'API ALARM: W={api_alarm.iloc[0]["Withdrawals"]}, D={api_alarm.iloc[0]["Deposits"]}')
    if not db_fee.empty:
        print(f'DB FEE: W={db_fee.iloc[0]["Withdrawals"]}, D={db_fee.iloc[0]["Deposits"]}')
else:
    print('Extraction failed')
