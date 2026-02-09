"""Batch test extraction on all Scotia Visa statements"""
import os
import sys
import traceback
from test_scotia_visa_complete import *

# Or import the logic directly
import re
import camelot
import pandas as pd
from datetime import datetime

scotia_visa_folder = 'data/Scotia Visa'

print("="*80)
print("BATCH TESTING ALL SCOTIA VISA STATEMENTS")
print("="*80)

# Get all PDF files
pdf_files = [f for f in os.listdir(scotia_visa_folder) if f.lower().endswith('.pdf')]
pdf_files.sort()

print(f"\nFound {len(pdf_files)} PDF files:")
for pdf in pdf_files:
    print(f"  - {pdf}")

results = []

month_map = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

for pdf_file in pdf_files:
    pdf_path = os.path.join(scotia_visa_folder, pdf_file)
    print(f"\n{'='*80}")
    print(f"Processing: {pdf_file}")
    print(f"{'='*80}")
    
    try:
        # Step 1: Extract year
        tables_stream = camelot.read_pdf(pdf_path, pages="1", flavor="stream")
        statement_start_year = None
        statement_end_year = None
        statement_period = None
        
        if len(tables_stream) > 0:
            table1 = tables_stream[0].df.fillna('')
            for idx in range(min(10, len(table1))):
                row = table1.iloc[idx]
                row_text = ' '.join([str(cell) for cell in row.tolist()])
                period_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})\s+-\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})', row_text, re.IGNORECASE)
                if period_match:
                    statement_period = period_match.group(0)
                    statement_start_year = period_match.group(2)
                    statement_end_year = period_match.group(4)
                    break
        
        if not statement_start_year:
            statement_start_year = "2024"
            statement_end_year = "2024"
        
        # Step 2: Extract balances
        all_tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
        opening_balance = None
        closing_balance = None
        
        for table_idx, table in enumerate(all_tables):
            df = table.df.fillna('')
            for idx in range(len(df)):
                row = df.iloc[idx]
                row_text = ' '.join([str(cell) for cell in row.tolist()])
                row_text_upper = row_text.upper()
                
                if 'PREVIOUS BALANCE' in row_text_upper and opening_balance is None:
                    amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                    if amount_match:
                        try:
                            opening_balance = float(amount_match.group(1).replace(',', ''))
                        except:
                            pass
                
                if ('NEW BALANCE' in row_text_upper or 'ACCOUNT BALANCE' in row_text_upper) and closing_balance is None:
                    amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                    if amount_match:
                        try:
                            closing_balance = float(amount_match.group(1).replace(',', ''))
                        except:
                            pass
        
        # Step 3: Extract transactions
        transactions = []
        transaction_table_indices = [1, 5]
        
        for table_idx in transaction_table_indices:
            if table_idx >= len(all_tables):
                continue
            
            table = all_tables[table_idx]
            df = table.df.fillna('')
            
            header_row_idx = None
            for idx in range(min(5, len(df))):
                row = df.iloc[idx]
                row_list = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
                row_text = ' '.join(row_list).upper()
                
                if 'REF.#' in row_text and 'AMOUNT' in row_text:
                    header_row_idx = idx
                    break
            
            if header_row_idx is None:
                continue
            
            check_row = header_row_idx + 1
            if check_row < len(df):
                check_row_text = ' '.join([str(cell) for cell in df.iloc[check_row].tolist()]).upper()
                has_ref_pattern = re.match(r'^\d{3}', str(df.iloc[check_row].iloc[0]).strip())
                start_row = check_row if has_ref_pattern else check_row + 1
            else:
                start_row = check_row
            
            for idx in range(start_row, len(df)):
                row = df.iloc[idx]
                row_list = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
                
                if not any(row_list):
                    continue
                
                row_text = ' '.join(row_list).upper()
                if 'SUB-TOTAL' in row_text or 'TOTAL' in row_text:
                    continue
                
                if len(row_list) < 5:
                    continue
                
                ref_str = row_list[0]
                trans_date_str = row_list[1]
                post_date_str = row_list[2]
                description = row_list[3]
                amount_str = row_list[4]
                
                if not re.match(r'^\d{3}$', ref_str):
                    continue
                
                date_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', post_date_str, re.IGNORECASE)
                if not date_match:
                    continue
                
                month_name = date_match.group(1).lower()
                day = int(date_match.group(2))
                month = month_map.get(month_name, 1)
                
                if statement_end_year and statement_start_year != statement_end_year:
                    if month <= 5:
                        year_to_use = int(statement_end_year)
                    else:
                        year_to_use = int(statement_start_year)
                else:
                    year_to_use = int(statement_start_year)
                
                try:
                    full_date = datetime(year_to_use, month, day)
                    date_str = full_date.strftime('%Y-%m-%d')
                except:
                    continue
                
                is_negative = amount_str.strip().endswith('-')
                amount_clean = amount_str.replace('-', '').replace('$', '').replace(',', '').strip()
                
                try:
                    amount = float(amount_clean)
                    if is_negative:
                        amount = -amount
                except:
                    continue
                
                transactions.append({
                    'Date': date_str,
                    'Description': description,
                    'Amount': amount
                })
        
        # Step 4: Calculate running balance
        if transactions:
            df = pd.DataFrame(transactions)
            df = df.sort_values('Date').reset_index(drop=True)
            
            if opening_balance is not None:
                df['Running_Balance'] = opening_balance + df['Amount'].cumsum()
            else:
                df['Running_Balance'] = df['Amount'].cumsum()
            
            final_running_balance = df['Running_Balance'].iloc[-1]
            
            # Verify
            balance_match = False
            if closing_balance is not None:
                difference = abs(final_running_balance - closing_balance)
                balance_match = difference < 0.01
            
            total_charges = df[df['Amount'] > 0]['Amount'].sum()
            total_payments = abs(df[df['Amount'] < 0]['Amount'].sum())
            
            results.append({
                'file': pdf_file,
                'status': 'SUCCESS',
                'statement_period': statement_period,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'transactions': len(df),
                'final_running_balance': final_running_balance,
                'balance_match': balance_match,
                'balance_difference': abs(final_running_balance - closing_balance) if closing_balance else None,
                'total_charges': total_charges,
                'total_payments': total_payments,
                'error': None
            })
            
            print(f"✅ Extracted {len(df)} transactions")
            print(f"   Opening: ${opening_balance:,.2f}" if opening_balance else "   Opening: Not found")
            print(f"   Closing: ${closing_balance:,.2f}" if closing_balance else "   Closing: Not found")
            print(f"   Final Running: ${final_running_balance:,.2f}")
            if closing_balance:
                if balance_match:
                    print(f"   ✅ Balance matches!")
                else:
                    print(f"   ❌ Balance mismatch: ${abs(final_running_balance - closing_balance):,.2f}")
        else:
            results.append({
                'file': pdf_file,
                'status': 'FAILED',
                'error': 'No transactions extracted',
                'transactions': 0
            })
            print(f"❌ No transactions extracted")
    
    except Exception as e:
        results.append({
            'file': pdf_file,
            'status': 'ERROR',
            'error': str(e),
            'transactions': 0
        })
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()

# Summary Report
print(f"\n\n{'='*80}")
print("SUMMARY REPORT")
print(f"{'='*80}")

successful = [r for r in results if r['status'] == 'SUCCESS']
failed = [r for r in results if r['status'] != 'SUCCESS']

print(f"\n✅ Successful: {len(successful)}/{len(results)}")
print(f"❌ Failed: {len(failed)}/{len(results)}")

if successful:
    print(f"\n{'File':<30} {'Transactions':<12} {'Opening':<12} {'Closing':<12} {'Running':<12} {'Match':<8}")
    print("-"*100)
    for r in successful:
        opening = f"${r['opening_balance']:,.2f}" if r['opening_balance'] else "N/A"
        closing = f"${r['closing_balance']:,.2f}" if r['closing_balance'] else "N/A"
        running = f"${r['final_running_balance']:,.2f}"
        match = "✅" if r['balance_match'] else "❌"
        print(f"{r['file']:<30} {r['transactions']:<12} {opening:<12} {closing:<12} {running:<12} {match:<8}")
        if not r['balance_match'] and r['balance_difference']:
            print(f"  ⚠️  Difference: ${r['balance_difference']:,.2f}")

if failed:
    print(f"\n❌ Failed Files:")
    for r in failed:
        print(f"  - {r['file']}: {r.get('error', 'Unknown error')}")

print(f"\n{'='*80}")





