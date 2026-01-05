"""Complete extraction test: year, balances, transactions, and running balance verification"""
import sys
import traceback
import re
import camelot
import pandas as pd
from datetime import datetime

pdf_path = sys.argv[1] if len(sys.argv) > 1 else 'data/Scotia Visa/1. Dec 2024.pdf'

print("="*80)
print("COMPLETE SCOTIA VISA EXTRACTION TEST")
print("="*80)
print(f"\nPDF: {pdf_path}\n")

try:
    # Step 1: Extract year from statement period
    print("="*80)
    print("STEP 1: EXTRACTING YEAR FROM STATEMENT PERIOD")
    print("="*80)
    
    tables_stream = camelot.read_pdf(pdf_path, pages="1", flavor="stream")
    statement_start_year = None
    statement_end_year = None
    statement_period = None
    
    # Look for statement period in first table
    if len(tables_stream) > 0:
        table1 = tables_stream[0].df.fillna('')
        for idx in range(min(10, len(table1))):
            row = table1.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            
            # Look for "Dec 3, 2024 - Jan 2, 2025" pattern
            period_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})\s+-\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})', row_text, re.IGNORECASE)
            if period_match:
                statement_period = period_match.group(0)
                statement_start_year = period_match.group(2)  # First year (2024)
                statement_end_year = period_match.group(4)    # Second year (2025)
                start_month = period_match.group(1).lower()
                end_month = period_match.group(3).lower()
                print(f"✅ Found statement period: {statement_period}")
                print(f"✅ Start year: {statement_start_year}, End year: {statement_end_year}")
                break
    
    if not statement_start_year:
        print("❌ Could not extract year, defaulting to 2024")
        statement_start_year = "2024"
        statement_end_year = "2024"
    
    # Step 2: Extract opening and closing balances
    print("\n" + "="*80)
    print("STEP 2: EXTRACTING OPENING AND CLOSING BALANCES")
    print("="*80)
    
    opening_balance = None
    closing_balance = None
    previous_balance = None
    new_balance = None
    
    # Look in all tables for balance information
    all_tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    for table_idx, table in enumerate(all_tables):
        df = table.df.fillna('')
        
        # Look for "PREVIOUS BALANCE" - usually in Account Summary section
        for idx in range(len(df)):
            row = df.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            row_text_upper = row_text.upper()
            
            # Look for "Previous balance" pattern
            if 'PREVIOUS BALANCE' in row_text_upper and opening_balance is None:
                # Extract amount from the row
                amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                if amount_match:
                    try:
                        opening_balance = float(amount_match.group(1).replace(',', ''))
                        print(f"✅ Found opening balance: ${opening_balance:,.2f} (Table {table_idx+1}, Row {idx})")
                        print(f"   Row text: {row_text[:100]}")
                    except:
                        pass
            
            # Look for "New Balance" or "Account Balance" - usually the final balance
            if ('NEW BALANCE' in row_text_upper or 'ACCOUNT BALANCE' in row_text_upper) and closing_balance is None:
                # Extract amount from the row
                amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                if amount_match:
                    try:
                        closing_balance = float(amount_match.group(1).replace(',', ''))
                        print(f"✅ Found closing balance: ${closing_balance:,.2f} (Table {table_idx+1}, Row {idx})")
                        print(f"   Row text: {row_text[:100]}")
                    except:
                        pass
    
    if not opening_balance:
        print("⚠️  Could not find opening balance")
    if not closing_balance:
        print("⚠️  Could not find closing balance")
    
    # Step 3: Extract transactions
    print("\n" + "="*80)
    print("STEP 3: EXTRACTING TRANSACTIONS")
    print("="*80)
    
    transactions = []
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # Find transaction tables (Tables 2 and 6, indices 1 and 5)
    transaction_table_indices = [1, 5]
    
    for table_idx in transaction_table_indices:
        transactions_before_table = len(transactions)
        if table_idx >= len(all_tables):
            continue
        
        table = all_tables[table_idx]
        df = table.df.fillna('')
        
        print(f"\nProcessing Table {table_idx+1}...")
        
        # Find header row (should have "REF.#" and "AMOUNT($)")
        header_row_idx = None
        for idx in range(min(5, len(df))):
            row = df.iloc[idx]
            row_list = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
            row_text = ' '.join(row_list).upper()
            
            if 'REF.#' in row_text and 'AMOUNT' in row_text:
                header_row_idx = idx
                print(f"  Found header at row {idx}")
                break
        
        if header_row_idx is None:
            print(f"  ⚠️  No header found, skipping table")
            continue
        
        # Process transaction rows (start after header)
        # In Table 2, there's an account name row after header, but in Table 6, transactions start immediately
        # Check if row after header looks like account name or transaction
        check_row = header_row_idx + 1
        if check_row < len(df):
            check_row_text = ' '.join([str(cell) for cell in df.iloc[check_row].tolist()]).upper()
            # If it has a REF number pattern, it's a transaction, otherwise skip it
            has_ref_pattern = re.match(r'^\d{3}', str(df.iloc[check_row].iloc[0]).strip())
            start_row = check_row if has_ref_pattern else check_row + 1
        else:
            start_row = check_row
        
        for idx in range(start_row, len(df)):
            row = df.iloc[idx]
            row_list = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
            
            # Skip empty rows
            if not any(row_list):
                continue
            
            # Skip subtotal rows
            row_text = ' '.join(row_list).upper()
            if 'SUB-TOTAL' in row_text or 'TOTAL' in row_text:
                continue
            
            # Check if this looks like a transaction (has REF number and dates)
            if len(row_list) < 5:
                continue
            
            ref_str = row_list[0]
            trans_date_str = row_list[1]
            post_date_str = row_list[2]
            description = row_list[3]
            amount_str = row_list[4]
            
            # Validate: REF should be 3 digits, dates should match pattern
            if not re.match(r'^\d{3}$', ref_str):
                continue
            
            # Parse date (use POST DATE - more accurate)
            date_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', post_date_str, re.IGNORECASE)
            if not date_match:
                continue
            
            month_name = date_match.group(1).lower()
            day = int(date_match.group(2))
            month = month_map.get(month_name, 1)
            
            # Determine which year to use based on month
            # If month is Jan-May and we have a statement period that spans years,
            # use the end year. Otherwise use start year.
            if statement_end_year and statement_start_year != statement_end_year:
                # Statement spans years (e.g., Dec 2024 - Jan 2025)
                # Use end year for Jan-May, start year for Jun-Dec
                if month <= 5:  # Jan-May
                    year_to_use = int(statement_end_year)
                else:  # Jun-Dec
                    year_to_use = int(statement_start_year)
            else:
                year_to_use = int(statement_start_year)
            
            # Convert to full date
            try:
                full_date = datetime(year_to_use, month, day)
                date_str = full_date.strftime('%Y-%m-%d')
            except:
                continue
            
            # Parse amount
            is_negative = amount_str.strip().endswith('-')
            amount_clean = amount_str.replace('-', '').replace('$', '').replace(',', '').strip()
            
            try:
                amount = float(amount_clean)
                if is_negative:
                    amount = -amount
            except:
                continue
            
            # Store transaction
            transactions.append({
                'Date': date_str,
                'Description': description,
                'Amount': amount
            })
        
        transactions_from_table = len(transactions) - transactions_before_table
        print(f"  Extracted {transactions_from_table} transactions from this table")
    
    print(f"\n✅ Total transactions extracted: {len(transactions)}")
    
    # Step 4: Create DataFrame and calculate running balance
    print("\n" + "="*80)
    print("STEP 4: CALCULATING RUNNING BALANCE")
    print("="*80)
    
    if transactions:
        df = pd.DataFrame(transactions)
        df = df.sort_values('Date').reset_index(drop=True)
        
        # Calculate running balance
        if opening_balance is not None:
            df['Running_Balance'] = opening_balance + df['Amount'].cumsum()
            print(f"✅ Starting with opening balance: ${opening_balance:,.2f}")
        else:
            df['Running_Balance'] = df['Amount'].cumsum()
            print("⚠️  No opening balance found, starting from 0")
        
        print(f"\nFirst 5 transactions:")
        print(df.head(5).to_string())
        
        print(f"\nLast 5 transactions:")
        print(df.tail(5).to_string())
        
        # Step 5: Verify against closing balance
        print("\n" + "="*80)
        print("STEP 5: VERIFYING AGAINST CLOSING BALANCE")
        print("="*80)
        
        final_running_balance = df['Running_Balance'].iloc[-1]
        
        print(f"Final running balance: ${final_running_balance:,.2f}")
        if closing_balance is not None:
            print(f"Statement closing balance: ${closing_balance:,.2f}")
            difference = abs(final_running_balance - closing_balance)
            if difference < 0.01:
                print(f"✅ MATCH! Difference: ${difference:,.2f}")
            else:
                print(f"❌ MISMATCH! Difference: ${difference:,.2f}")
        else:
            print("⚠️  No closing balance found for comparison")
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Statement Period: {statement_period if statement_period else 'Not found'}")
        print(f"Opening Balance: ${opening_balance:,.2f}" if opening_balance else "Opening Balance: Not found")
        print(f"Closing Balance: ${closing_balance:,.2f}" if closing_balance else "Closing Balance: Not found")
        print(f"Total Transactions: {len(df)}")
        print(f"Final Running Balance: ${final_running_balance:,.2f}")
        print(f"Total Charges: ${df[df['Amount'] > 0]['Amount'].sum():,.2f}")
        print(f"Total Payments: ${abs(df[df['Amount'] < 0]['Amount'].sum()):,.2f}")
        
        # Verify calculation
        if opening_balance and closing_balance:
            calculated_closing = opening_balance + df['Amount'].sum()
            print(f"\nVerification:")
            print(f"  Opening: ${opening_balance:,.2f}")
            print(f"  + Net transactions: ${df['Amount'].sum():,.2f}")
            print(f"  = Calculated closing: ${calculated_closing:,.2f}")
            print(f"  Actual closing: ${closing_balance:,.2f}")
            print(f"  Difference: ${abs(calculated_closing - closing_balance):,.2f}")
    else:
        print("❌ No transactions extracted")

except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    traceback.print_exc()

