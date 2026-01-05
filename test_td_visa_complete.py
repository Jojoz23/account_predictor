"""Complete extraction test for TD Visa: year, balances, transactions, and running balance verification"""
import sys
import traceback
import re
import camelot
import pandas as pd
from datetime import datetime

pdf_path = sys.argv[1] if len(sys.argv) > 1 else 'data/TD VISA 6157/1. Dec 2024.pdf'

print("="*80)
print("COMPLETE TD VISA EXTRACTION TEST")
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
    
    # Look for statement period in all tables (TD Visa has it in Table 1)
    for table_idx, table in enumerate(tables_stream):
        df = table.df.fillna('')
        for idx in range(len(df)):
            row = df.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            
            # Pattern: "STATEMENT PERIOD: May 06, 2025 to June 05, 2025"
            # Try simpler pattern that matches the date range directly
            period_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})\s+to\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})', row_text, re.IGNORECASE)
            # Only accept if "STATEMENT PERIOD" appears in the row
            if period_match and 'STATEMENT PERIOD' in row_text.upper():
                statement_period = period_match.group(0)
                statement_start_year = period_match.group(2)
                statement_end_year = period_match.group(4)
                print(f"\nFound statement period in Table {table_idx+1}, Row {idx}: {statement_period}")
                print(f"Start year: {statement_start_year}, End year: {statement_end_year}")
                break
            if period_match:
                statement_period = period_match.group(0)
                statement_start_year = period_match.group(2)
                statement_end_year = period_match.group(4)
                print(f"\nFound statement period in Table {table_idx+1}, Row {idx}: {statement_period}")
                print(f"Start year: {statement_start_year}, End year: {statement_end_year}")
                break
        if statement_start_year:
            break
            
            # Pattern 2: "Dec 1, 2024 - Jan 1, 2025" (with dash)
            period_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+(\d{4})\s+-\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+(\d{4})', row_text, re.IGNORECASE)
            if period_match:
                statement_period = period_match.group(0)
                statement_start_year = period_match.group(2)
                statement_end_year = period_match.group(4)
                print(f"\nFound statement period: {statement_period}")
                print(f"Start year: {statement_start_year}, End year: {statement_end_year}")
                break
    
    if not statement_start_year:
        print("\nWarning: Could not extract year from statement period")
        print("   Checking all tables for year information...")
        # Try to find year in any table
        for table_idx, table in enumerate(tables_stream):
            df = table.df.fillna('')
            for idx in range(min(20, len(df))):
                row_text = ' '.join([str(cell) for cell in df.iloc[idx].tolist()])
                year_match = re.search(r'\b(202[0-9]|203[0-9])\b', row_text)
                if year_match:
                    year = year_match.group(1)
                    print(f"   Found year {year} in Table {table_idx+1}, Row {idx}")
                    statement_start_year = year
                    statement_end_year = year
                    break
            if statement_start_year:
                break
    
    if not statement_start_year:
        print("Could not extract year, defaulting to 2024")
        statement_start_year = "2024"
        statement_end_year = "2024"
    
    # Step 2: Extract opening and closing balances
    print("\n" + "="*80)
    print("STEP 2: EXTRACTING OPENING AND CLOSING BALANCES")
    print("="*80)
    
    opening_balance = None
    closing_balance = None
    
    # Read PDF text to find balances
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page_num in range(min(3, len(pdf.pages))):
            text += pdf.pages[page_num].extract_text() or ""
    
    # Look for TD Visa balance patterns
    # TD Visa has "PREVIOUS STATEMENT BALANCE" in the transaction table
    # Also check in text and tables
    opening_patterns = [
        r'PREVIOUS\s+STATEMENT\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Previous\s+Statement\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Previous\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Opening\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
    ]
    
    # Check in transaction tables first
    for table_idx, table in enumerate(tables_stream):
        df = table.df.fillna('')
        for idx in range(len(df)):
            row_text = ' '.join([str(cell).upper() for cell in df.iloc[idx].tolist()])
            for pattern in opening_patterns:
                match = re.search(pattern, row_text)
                if match:
                    opening_balance = float(match.group(1).replace(',', ''))
                    print(f"Found opening balance in Table {table_idx+1}, Row {idx}: ${opening_balance:,.2f}")
                    break
            if opening_balance:
                break
        if opening_balance:
            break
    
    # Also check in text
    if not opening_balance:
        for pattern in opening_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                opening_balance = float(match.group(1).replace(',', ''))
                print(f"Found opening balance: ${opening_balance:,.2f}")
                break
    
    # Pattern: "New Balance" or "Closing Balance" or "Total Amount Due"
    # TD Visa shows "TOTAL NEW BALANCE" or "NEW BALANCE"
    closing_patterns = [
        r'TOTAL\s+NEW\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'NEW\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'New\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Closing\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Total\s+Amount\s+Due[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Statement\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
    ]
    
    # Re-read all pages for closing balance (might be on later pages)
    tables_stream_balances = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    
    # Check in tables first
    for table_idx, table in enumerate(tables_stream_balances):
        df = table.df.fillna('')
        for idx in range(len(df)):
            row_text = ' '.join([str(cell).upper() for cell in df.iloc[idx].tolist()])
            for pattern in closing_patterns:
                match = re.search(pattern, row_text)
                if match:
                    closing_balance = float(match.group(1).replace(',', ''))
                    print(f"Found closing balance in Table {table_idx+1}, Row {idx}: ${closing_balance:,.2f}")
                    break
            if closing_balance:
                break
        if closing_balance:
            break
    
    # Also check in text
    if not closing_balance:
        for pattern in closing_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                closing_balance = float(match.group(1).replace(',', ''))
                print(f"Found closing balance: ${closing_balance:,.2f}")
                break
    
    if opening_balance is None:
        print("Warning: Could not find opening balance")
    if closing_balance is None:
        print("Warning: Could not find closing balance")
    
    # Step 3: Extract transactions
    print("\n" + "="*80)
    print("STEP 3: EXTRACTING TRANSACTIONS")
    print("="*80)
    
    transactions = []
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # Re-read all pages for transactions (TD Visa statements span multiple pages)
    tables_stream_all = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    print(f"\nTotal tables found: {len(tables_stream_all)}")
    print("Scanning all tables for transaction headers...")
    for table_idx, table in enumerate(tables_stream_all):
        df = table.df.fillna('')
        print(f"\nTable {table_idx+1}: {len(df)} rows, {len(df.columns)} columns")
        
        # Check if this looks like a transaction table
        # Look for headers like "Date", "Description", "Amount"
        header_found = False
        date_col = None
        desc_col = None
        amount_col = None
        
        # Check more rows for headers (TD Visa continuation pages might have headers later)
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            row_text = ' '.join([str(cell).upper() for cell in row.tolist()])
            
            # Check for transaction table headers
            # TD Visa format 1: "DATE DATE ACTIVITY DESCRIPTION AMOUNT($)" (separate columns)
            # TD Visa format 2: "DATE\nDATE\nACTIVITY DESCRIPTION" in one column, "AMOUNT($)" in another (November format)
            if 'DATE' in row_text and ('DESCRIPTION' in row_text or 'MERCHANT' in row_text or 'DETAILS' in row_text or 'ACTIVITY' in row_text) and 'AMOUNT' in row_text:
                header_found = True
                print(f"  Found transaction header at row {idx}")
                print(f"  Row text: {row_text[:200]}")
                
                # Check if this is the combined format (dates and description in one cell)
                is_combined_format = False
                for col_idx, cell in enumerate(row):
                    cell_str = str(cell)
                    if '\n' in cell_str and 'DATE' in cell_str.upper() and ('DESCRIPTION' in cell_str.upper() or 'ACTIVITY' in cell_str.upper()):
                        is_combined_format = True
                        date_col = col_idx  # Dates and description are in this column
                        desc_col = col_idx  # Same column
                        print(f"  Detected combined format: dates and description in column {col_idx}")
                        break
                
                if not is_combined_format:
                    # Find column indices for separate columns format
                    # TD Visa has two DATE columns - use the first one (transaction date)
                    for col_idx, cell in enumerate(row):
                        cell_upper = str(cell).upper()
                        if 'DATE' in cell_upper and date_col is None:
                            date_col = col_idx  # Use first DATE column (transaction date)
                        if ('DESCRIPTION' in cell_upper or 'MERCHANT' in cell_upper or 'DETAILS' in cell_upper or 'ACTIVITY' in cell_upper) and desc_col is None:
                            desc_col = col_idx
                        if 'AMOUNT' in cell_upper and amount_col is None:
                            amount_col = col_idx
                
                # Find amount column if not already found
                if amount_col is None:
                    for col_idx, cell in enumerate(row):
                        cell_upper = str(cell).upper()
                        if 'AMOUNT' in cell_upper:
                            amount_col = col_idx
                            break
                
                print(f"  Column indices - Date: {date_col}, Desc: {desc_col}, Amount: {amount_col}")
                break
        
        if header_found and date_col is not None and desc_col is not None and amount_col is not None:
            # Extract transactions from this table
            start_row = idx + 1
            transactions_before = len(transactions)
            
            # Check if this is combined format (dates and description in same cell)
            is_combined_format = (date_col == desc_col)
            
            for row_idx in range(start_row, len(df)):
                row = df.iloc[row_idx]
                
                if is_combined_format:
                    # Combined format: "MERCHANT NAME\nOCT 7\nOCT 8" in one cell
                    combined_cell = str(row.iloc[date_col]).strip()
                    if not combined_cell or combined_cell == 'nan':
                        continue
                    
                    # Split by newlines
                    parts = [p.strip() for p in combined_cell.split('\n') if p.strip()]
                    if len(parts) < 2:
                        continue
                    
                    # First part is description, second is transaction date, third (if exists) is posting date
                    desc_str = parts[0]
                    date_str = parts[1] if len(parts) > 1 else ''
                else:
                    # Separate columns format
                    date_str = str(row.iloc[date_col]).strip()
                    desc_str = str(row.iloc[desc_col]).strip()
                
                amount_str = str(row.iloc[amount_col]).strip()
                
                # Skip empty rows
                if not date_str or date_str == 'nan':
                    continue
                
                # Skip balance rows (like "PREVIOUS STATEMENT BALANCE", "TOTAL NEW BALANCE")
                # But don't skip if it's a transaction row that happens to have "BALANCE" in another column
                row_text_upper = ' '.join([str(cell).upper() for cell in row.tolist()])
                
                # Only skip if the description column itself contains balance-related text
                desc_upper = str(row.iloc[desc_col]).upper() if desc_col is not None and desc_col < len(row) else ''
                
                # Check if this row has a valid date first (before deciding to skip)
                date_match_check = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})', date_str, re.IGNORECASE)
                
                # Only skip balance rows if they don't have a valid transaction date
                if 'PREVIOUS' in desc_upper and 'BALANCE' in desc_upper and not date_match_check:
                    continue
                if 'TOTAL' in desc_upper and 'NEW BALANCE' in desc_upper and not date_match_check:
                    continue
                # Don't skip rows with "CALCULATING YOUR BALANCE" if they have a valid date (it's just in another column)
                if 'CALCULATING' in row_text_upper and 'BALANCE' in row_text_upper and not date_match_check:
                    continue
                
                # Parse date (TD Visa format: "MAY 8" or "May 8" - use first date which is transaction date)
                # TD Visa has two date columns - first is transaction date, second is posting date
                date_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})', date_str, re.IGNORECASE)
                if not date_match:
                    continue
                
                month_name = date_match.group(1).lower()
                day = int(date_match.group(2))
                month = month_map.get(month_name, 1)
                
                # Determine year
                if statement_end_year and statement_start_year and statement_start_year != statement_end_year:
                    if month <= 5:
                        year_to_use = int(statement_end_year)
                    else:
                        year_to_use = int(statement_start_year)
                else:
                    year_to_use = int(statement_start_year)
                
                try:
                    full_date = datetime(year_to_use, month, day)
                    date_str_formatted = full_date.strftime('%Y-%m-%d')
                except:
                    continue
                
                # Parse amount
                # TD Visa format: amounts can be attached to description like "$140.10FULLSCRIPT"
                # Also handle negative amounts like "-$523.92"
                amount_clean = amount_str.replace(',', '').replace('$', '').strip()
                is_negative = amount_str.strip().startswith('-') or amount_clean.startswith('-')
                
                # Remove minus sign for parsing
                amount_clean = amount_clean.replace('-', '').strip()
                
                # Extract just the number part (might be attached to text)
                amount_match = re.search(r'([\d,]+\.?\d{0,2})', amount_clean)
                if not amount_match:
                    continue
                
                try:
                    amount = float(amount_match.group(1).replace(',', ''))
                    if is_negative:
                        amount = -amount
                except:
                    continue
                
                transactions.append({
                    'Date': date_str_formatted,
                    'Description': desc_str,
                    'Amount': amount
                })
            
            new_transactions = len(transactions) - transactions_before
            print(f"  Extracted {new_transactions} new transactions from Table {table_idx+1}")
            print(f"  Total transactions so far: {len(transactions)}")
    
    if not transactions:
        print("\nWarning: No transactions found. Checking table structure...")
        # Print first few rows of each table
        for table_idx, table in enumerate(tables_stream[:3]):
            df = table.df.fillna('')
            print(f"\nTable {table_idx+1} first 5 rows:")
            for idx in range(min(5, len(df))):
                print(f"  Row {idx}: {df.iloc[idx].tolist()}")
    
    # Step 4: Calculate running balance
    print("\n" + "="*80)
    print("STEP 4: CALCULATING RUNNING BALANCE")
    print("="*80)
    
    if transactions and opening_balance:
        df = pd.DataFrame(transactions)
        df = df.sort_values('Date').reset_index(drop=True)
        
        # Calculate running balance
        df['Running_Balance'] = opening_balance + df['Amount'].cumsum()
        
        print(f"\nTotal transactions: {len(df)}")
        print(f"Opening balance: ${opening_balance:,.2f}")
        print(f"Sum of all transaction amounts: ${df['Amount'].sum():,.2f}")
        print(f"Expected closing balance: ${opening_balance + df['Amount'].sum():,.2f}")
        print(f"Final running balance: ${df['Running_Balance'].iloc[-1]:,.2f}")
        
        if closing_balance is not None:
            difference = abs(df['Running_Balance'].iloc[-1] - closing_balance)
            if difference < 0.01:
                print(f"OK: Running balance matches closing balance (${closing_balance:,.2f})")
            else:
                print(f"Warning: Running balance mismatch:")
                print(f"   Calculated: ${df['Running_Balance'].iloc[-1]:,.2f}")
                print(f"   Statement: ${closing_balance:,.2f}")
                print(f"   Difference: ${difference:,.2f}")
        
        print("\nFirst 5 transactions:")
        print(df[['Date', 'Description', 'Amount', 'Running_Balance']].head(5).to_string())
        print("\nLast 5 transactions:")
        print(df[['Date', 'Description', 'Amount', 'Running_Balance']].tail(5).to_string())
    else:
        print("Warning: Cannot calculate running balance - missing transactions or opening balance")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    
except Exception as e:
    print(f"\nERROR: {str(e)}")
    traceback.print_exc()

