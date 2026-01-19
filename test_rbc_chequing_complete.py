#!/usr/bin/env python3
"""
RBC Chequing Account Statement Extractor
Extracts transactions from RBC Chequing PDF statements
"""

import camelot
import pdfplumber
import pandas as pd
import re
from datetime import datetime
from pathlib import Path

def extract_rbc_chequing_statement(pdf_path):
    """
    Extract transactions from RBC Chequing statement
    
    Returns:
        tuple: (DataFrame, opening_balance, closing_balance, statement_year)
    """
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    
    # Extract text for year and balance detection
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    # Extract statement period to get years
    # Handle formats like "December20,2024toJanuary22,2025" (no spaces around "to")
    # Month names are letters only, then comes a digit for the day
    period_match = re.search(r'([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})\s*to\s*([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})', full_text, re.IGNORECASE)
    statement_start_year = None
    statement_end_year = None
    statement_start_month = None
    statement_end_month = None
    
    if period_match:
        start_month_name = period_match.group(1)
        start_day = int(period_match.group(2))
        statement_start_year = int(period_match.group(3))
        end_month_name = period_match.group(4)
        end_day = int(period_match.group(5))
        statement_end_year = int(period_match.group(6))
        
        # Map month names to numbers
        month_map = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
            'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
            'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
            'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }
        statement_start_month = month_map.get(start_month_name.lower(), 1)
        statement_end_month = month_map.get(end_month_name.lower(), 1)
        
        # Default statement year (use end year for most transactions)
        statement_year = statement_end_year
    else:
        # Fallback: look for any 4-digit year
        year_match = re.search(r'\b(202[0-9]|203[0-9])\b', full_text)
        if year_match:
            statement_year = int(year_match.group(1))
            statement_start_year = statement_year
            statement_end_year = statement_year
        else:
            statement_year = 2025  # Default fallback
            statement_start_year = 2025
            statement_end_year = 2025
    
    # Extract opening balance
    # Handle concatenated text like "OpeningbalanceonJanuary22,2025 $289.41" or "-$1,345.99"
    opening_patterns = [
        r'openingbalanceon\w+\d{1,2},\s*\d{4}\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign if present
        r'opening\s*balance\s*on\s*\w+\s*\d{1,2},\s*\d{4}\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
        r'opening\s*balance\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
    ]
    for pattern in opening_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                sign = match.group(1)  # This will be '-' or '$' or '-$' or empty
                value = float(match.group(2).replace(',', ''))
                opening_balance = -value if '-' in sign else value
                break
            except:
                continue
    
    # Also check for opening balance in transaction table
    if opening_balance is None:
        opening_balance_match = re.search(r'opening\s*balance\s*(-?\$?)([\d,]+\.?\d*)', full_text, re.IGNORECASE)
        if opening_balance_match:
            try:
                sign = opening_balance_match.group(1)
                value = float(opening_balance_match.group(2).replace(',', ''))
                opening_balance = -value if '-' in sign else value
            except:
                pass
    
    # Extract closing balance
    # Handle concatenated text like "ClosingbalanceonFebruary21,2025 = $6.87" or "= -$3,330.46"
    closing_patterns = [
        r'closingbalanceon\w+\d{1,2},\s*\d{4}\s*=\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
        r'closing\s*balance\s*on\s*\w+\s*\d{1,2},\s*\d{4}\s*=\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
        r'closing\s*balance\s*=\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
        r'closing\s*balance\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
    ]
    for pattern in closing_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                sign = match.group(1)  # This will be '-' or '$' or '-$' or empty
                value = float(match.group(2).replace(',', ''))
                closing_balance = -value if '-' in sign else value
                break
            except:
                continue
    
    # Extract transactions using Camelot with stream flavor
    try:
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        
        # Find all transaction tables (may be multiple for multi-page statements)
        transaction_tables = []
        for table in tables:
            df = table.df.copy()
            
            # Drop fully empty columns (all NaN or empty strings across ALL rows)
            cols_to_drop = []
            for col_idx in range(len(df.columns)):
                col_data = df.iloc[:, col_idx].astype(str).str.strip()
                # Check if entire column is empty (excluding empty string variations)
                if col_data.isin(['', 'nan', 'None', 'NaN']).all():
                    cols_to_drop.append(col_idx)
            
            # Drop columns in reverse order to maintain indices
            if cols_to_drop:
                df = df.drop(df.columns[cols_to_drop], axis=1)
                # Reset column indices after dropping
                df.columns = range(len(df.columns))
            
            # Check if this table has transaction headers
            if len(df.columns) >= 4:
                # Check for transaction-related headers in first few rows
                for row_idx in range(min(5, len(df))):
                    header_text = ' '.join(df.iloc[row_idx].astype(str)).lower()
                    if 'date' in header_text and ('description' in header_text or 'debits' in header_text or 'credits' in header_text or 'continued' in header_text):
                        transaction_tables.append((df, row_idx))
                        break
        
        if not transaction_tables:
            print("Could not find transaction table")
            return None, opening_balance, closing_balance, statement_year
        
        # Detect column indices from header row dynamically
        # Default to standard positions but detect from actual headers
        date_col = 0
        desc_col = 1
        debit_col = 2
        credit_col = 3
        balance_col = 4
        
        # Try to detect columns from each transaction table's header (may differ)
        # We'll detect columns per table since continuation tables might have different layouts
        def detect_columns_from_header(header_row):
            """Detect column indices from a header row"""
            detected = {
                'date': None,
                'desc': None,
                'debit': None,
                'credit': None,
                'balance': None
            }
            for col_idx in range(len(header_row)):
                cell_text = str(header_row.iloc[col_idx]).lower().strip()
                if 'date' in cell_text and detected['date'] is None:
                    detected['date'] = col_idx
                elif 'description' in cell_text and detected['desc'] is None:
                    detected['desc'] = col_idx
                elif ('cheques' in cell_text or 'debits' in cell_text) and '$' in cell_text and detected['debit'] is None:
                    detected['debit'] = col_idx
                elif ('deposits' in cell_text or 'credits' in cell_text) and '$' in cell_text and detected['credit'] is None:
                    detected['credit'] = col_idx
                elif 'balance' in cell_text and '$' in cell_text and detected['balance'] is None:
                    detected['balance'] = col_idx
            return detected
        
        # Detect from first table as default
        if transaction_tables:
            header_table, header_row_idx = transaction_tables[0]
            header_row = header_table.iloc[header_row_idx]
            detected = detect_columns_from_header(header_row)
            if detected['date'] is not None:
                date_col = detected['date']
            if detected['desc'] is not None:
                desc_col = detected['desc']
            if detected['debit'] is not None:
                debit_col = detected['debit']
            if detected['credit'] is not None:
                credit_col = detected['credit']
            if detected['balance'] is not None:
                balance_col = detected['balance']
        
        # Process rows starting after header
        current_date = None
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        # Process all transaction tables
        pending_transaction = None  # For multi-line transactions
        found_closing_balance = False  # Track if we've seen closing balance
        
        for table_idx, (transaction_table, header_row_idx) in enumerate(transaction_tables):
            # Skip if we've already found closing balance
            if found_closing_balance:
                break
            
            # Detect columns for this specific table (continuation tables may have different layouts)
            header_row = transaction_table.iloc[header_row_idx]
            detected = detect_columns_from_header(header_row)
            
            # Use detected columns for this table, or fall back to defaults
            table_date_col = detected['date'] if detected['date'] is not None else date_col
            table_desc_col = detected['desc'] if detected['desc'] is not None else desc_col
            table_debit_col = detected['debit'] if detected['debit'] is not None else debit_col
            table_credit_col = detected['credit'] if detected['credit'] is not None else credit_col
            table_balance_col = detected['balance'] if detected['balance'] is not None else balance_col
            for i in range(header_row_idx + 1, len(transaction_table)):
                row = transaction_table.iloc[i]
                
                # Skip empty rows
                if row.isna().all() or (row.astype(str).str.strip() == '').all():
                    continue
                
                # Check for opening/closing balance rows
                row_text = ' '.join(row.astype(str)).lower()
                if 'opening balance' in row_text:
                    # Opening balance already extracted from text
                    continue
                if 'closing balance' in row_text:
                    # Closing balance already extracted from text
                    # Stop processing - no more transactions after this
                    found_closing_balance = True
                    break
                if 'account fees' in row_text or re.match(r'^\d+\s+of\s+\d+', row_text) or 'business account statement' in row_text.lower():
                    # Skip header rows on continuation pages
                    continue
                
                # Extract date using this table's column
                date_str = str(row.iloc[table_date_col]).strip() if table_date_col < len(row) else ''
                
                # Check if this row has a date (format: "03 Feb" or "03Feb" or "22 Jan")
                date_match = re.match(r'^(\d{1,2})\s*(\w{3})', date_str)
                if date_match:
                    day = int(date_match.group(1))
                    month_abbr = date_match.group(2).capitalize()
                    month = month_map.get(month_abbr, 1)
                    try:
                        # Determine correct year for this date
                        # If statement spans two years (e.g., Dec 2024 to Jan 2025),
                        # use the appropriate year based on the month
                        transaction_year = statement_year
                        if statement_start_year is not None and statement_start_year != statement_end_year:
                            # Statement spans two years - determine correct year based on month
                            # If the month matches the start month, use start year
                            # If the month matches the end month, use end year
                            if month == statement_start_month:
                                transaction_year = statement_start_year
                            elif month == statement_end_month:
                                transaction_year = statement_end_year
                            elif month < statement_start_month:
                                # Month is before start month (e.g., Nov in a Dec-Jan statement) - unlikely but use start year
                                transaction_year = statement_start_year
                            elif month > statement_end_month:
                                # Month is after end month - shouldn't happen, but use end year
                                transaction_year = statement_end_year
                            else:
                                # Month is between start and end (shouldn't happen for 2-month span, but handle it)
                                # For a Dec-Jan span, there are no months between, so this is a fallback
                                transaction_year = statement_end_year
                        
                        current_date = datetime(transaction_year, month, day)
                        pending_transaction = None  # Reset pending transaction on new date
                    except:
                        continue
                
                # If no date, use previous date (continuation of same day)
                if current_date is None:
                    continue
                
                # Extract description using this table's column - preserve exact format
                desc = str(row.iloc[table_desc_col]) if table_desc_col < len(row) else ''
                # Only strip leading/trailing whitespace, preserve internal formatting
                desc = desc.strip()
                # Replace newlines with single space for consistency, but preserve other formatting
                if '\n' in desc:
                    desc = ' '.join(desc.split())  # Normalize whitespace but keep as single line
                
                # Extract amounts using this table's columns
                # Store the raw strings so we can identify which columns contain amounts later
                debit_str = str(row.iloc[table_debit_col]).strip() if table_debit_col < len(row) else ''
                credit_str = str(row.iloc[table_credit_col]).strip() if table_credit_col < len(row) else ''
                balance_str = str(row.iloc[table_balance_col]).strip() if table_balance_col < len(row) else ''
                
                # Check if amounts are in description column (multi-line transaction)
                # Look for amounts only in the proper amount columns (debit, credit, balance)
                # Don't scan description column for amounts to avoid hex codes
                all_amounts = []
                amount_columns = [table_debit_col, table_credit_col, table_balance_col]
                for col_idx in amount_columns:
                    if col_idx is not None and col_idx < len(row):
                        cell_str = str(row.iloc[col_idx]).strip()
                        # Look for proper amount patterns: must have decimal point and two digits after
                        # Pattern: optional space, digits (with optional commas), decimal point, exactly 2 digits, optional space or end
                        amount_matches = re.findall(r'(?:^|\s)([\d,]+\.\d{2})(?:\s|$)', cell_str)
                        for match in amount_matches:
                            try:
                                amount = float(match.replace(',', ''))
                                # Additional validation: reasonable amount range
                                if 0.01 <= amount <= 100000:
                                    all_amounts.append(amount)
                            except:
                                pass
                
                # Parse amounts
                debit = None
                credit = None
                balance = None
                
                # Remove commas and dollar signs
                if debit_str and debit_str.lower() not in ['', 'nan', 'none']:
                    debit_match = re.search(r'([\d,]+\.?\d*)', debit_str)
                    if debit_match:
                        try:
                            debit = float(debit_match.group(1).replace(',', ''))
                        except:
                            pass
                
                if credit_str and credit_str.lower() not in ['', 'nan', 'none']:
                    credit_match = re.search(r'([\d,]+\.?\d*)', credit_str)
                    if credit_match:
                        try:
                            credit = float(credit_match.group(1).replace(',', ''))
                        except:
                            pass
                
                if balance_str and balance_str.lower() not in ['', 'nan', 'none']:
                    # Handle negative balances (e.g., "-267.90" or "-$1,345.99")
                    balance_match = re.search(r'(-?\$?)([\d,]+\.?\d*)', balance_str)
                    if balance_match:
                        try:
                            sign = balance_match.group(1)  # '-' or '$' or '-$' or empty
                            value = float(balance_match.group(2).replace(',', ''))
                            balance = -value if '-' in sign else value
                        except:
                            pass
                
                # Handle multi-line transactions (description spans multiple rows)
                # If we have a pending transaction, try to merge with current row
                if pending_transaction:
                    # FIRST: Collect ALL text from ALL columns before processing amounts
                    # This ensures we capture reference codes, hex codes, and all description parts
                    all_desc_parts = []
                    
                    # Add description from description column
                    if desc and desc.lower() not in ['', 'nan', 'none']:
                        desc_clean = desc.strip()
                        if desc_clean:
                            all_desc_parts.append(desc_clean)
                    
                    # Check ALL other columns for additional description parts
                    # Include everything except date and amounts we'll extract
                    for col_idx in range(len(row)):
                        # Skip date column
                        if col_idx == table_date_col:
                            continue
                        # Skip description column (already added)
                        if col_idx == table_desc_col:
                            continue
                        
                        col_val = str(row.iloc[col_idx]).strip()
                        if not col_val or col_val.lower() in ['', 'nan', 'none']:
                            continue
                        
                        # Check if this is an amount column - compare with strings we'll parse
                        is_amount = False
                        if col_idx == table_debit_col:
                            if debit_str and col_val == debit_str:
                                is_amount = True
                        elif col_idx == table_credit_col:
                            if credit_str and col_val == credit_str:
                                is_amount = True
                        elif col_idx == table_balance_col:
                            if balance_str and col_val == balance_str:
                                is_amount = True
                        
                        # Include everything that's not an amount
                        if not is_amount:
                            all_desc_parts.append(col_val)
                    
                    # Combine all description parts
                    if all_desc_parts:
                        pending_transaction['Description'] += ' ' + ' '.join(all_desc_parts)
                    
                    # NOW extract amounts from proper columns
                    if credit and not pending_transaction.get('Deposits'):
                        pending_transaction['Deposits'] = credit
                    if debit and not pending_transaction.get('Withdrawals'):
                        pending_transaction['Withdrawals'] = debit
                    if balance:
                        pending_transaction['Balance'] = balance
                    
                    # Check if we have amounts anywhere in this row (including description column)
                    if all_amounts and not pending_transaction.get('Deposits') and not pending_transaction.get('Withdrawals'):
                        # Typically first amount is credit, last is balance
                        if len(all_amounts) >= 2:
                            pending_transaction['Deposits'] = all_amounts[0]  # First is usually credit
                            pending_transaction['Balance'] = all_amounts[-1]  # Last is balance
                        elif len(all_amounts) == 1:
                            pending_transaction['Deposits'] = all_amounts[0]
                    
                    # Look ahead to next 2 rows for amounts if still not found
                    # Only check proper amount columns (not description column) to avoid hex codes
                    if not pending_transaction.get('Deposits') and not pending_transaction.get('Withdrawals'):
                        for lookahead_idx in range(i + 1, min(i + 3, len(transaction_table))):
                            lookahead_row = transaction_table.iloc[lookahead_idx]
                            # Extract amounts only from proper amount columns
                            lookahead_amounts = []
                            amount_columns = [table_debit_col, table_credit_col, table_balance_col]
                            for col_idx in amount_columns:
                                if col_idx is not None and col_idx < len(lookahead_row):
                                    cell_str = str(lookahead_row.iloc[col_idx]).strip()
                                    # Only match proper decimal amounts
                                    amount_matches = re.findall(r'([\d,]+\.\d{2})', cell_str)
                                    for match in amount_matches:
                                        try:
                                            amount = float(match.replace(',', ''))
                                            if 0.01 <= amount <= 100000:
                                                lookahead_amounts.append(amount)
                                        except:
                                            pass
                            
                            if lookahead_amounts:
                                # Typically: debit/credit, then balance
                                if len(lookahead_amounts) >= 2:
                                    pending_transaction['Deposits'] = lookahead_amounts[0]
                                    pending_transaction['Balance'] = lookahead_amounts[-1]
                                elif len(lookahead_amounts) == 1:
                                    pending_transaction['Deposits'] = lookahead_amounts[0]
                                break
                    
                    # Also check raw text if still no amounts found (but not if we've seen closing balance)
                    if not found_closing_balance and not pending_transaction.get('Deposits') and not pending_transaction.get('Withdrawals'):
                        # Find the transaction in raw text and extract amounts
                        desc_lower = pending_transaction['Description'].lower()
                        # Try multiple search terms from the description
                        search_terms = []
                        if 'computron' in desc_lower or 'autodeposit' in desc_lower:
                            # For these transactions, search more specifically
                            if 'computron' in desc_lower:
                                search_terms = ['computron']
                            elif 'autodeposit' in desc_lower:
                                search_terms = ['autodeposit', 'e-transfer']
                        else:
                            # Use last significant word
                            desc_parts = [w for w in desc_lower.split() if len(w) > 3]
                            if desc_parts:
                                search_terms = [desc_parts[-1][:10]]
                        
                        for search_term in search_terms:
                            idx = full_text.lower().find(search_term)
                            if idx >= 0:
                                # Look for amounts in a wider context after the search term
                                start_pos = idx + len(search_term)
                                context = full_text[start_pos:min(len(full_text), start_pos + 200)]
                                
                                # Find the line that contains the amounts
                                lines = context.split('\n')
                                for line in lines:
                                    line_stripped = line.strip()
                                    # Look for lines with amounts (decimal format)
                                    if re.search(r'\d+\.\d{2}', line_stripped):
                                        # This line has amounts - extract description part before amounts
                                        # Split the line: description part and amounts
                                        # Match pattern like "456d00704...113.00 297.80"
                                        # Try to separate description from amounts
                                        amount_pattern = r'([\d,]+\.\d{2})'
                                        amounts_in_line = re.findall(amount_pattern, line_stripped)
                                        if amounts_in_line:
                                            # Remove amounts to get description part
                                            desc_part = re.sub(amount_pattern, '', line_stripped)
                                            desc_part = re.sub(r'\s+', ' ', desc_part).strip()
                                            # Only add if it looks like a description (not headers, dates, etc.)
                                            if desc_part and len(desc_part) > 3:
                                                # Check if it's not a header/date line
                                                # Include all description parts, don't filter
                                                pending_transaction['Description'] += ' ' + desc_part
                                        
                                        # Extract amounts from this line
                                        # Look for properly formatted amounts (X.XX format) that are NOT part of hex codes
                                        # Hex codes are long alphanumeric strings - amounts should be separated by spaces
                                        # Pattern: space + digits + .XX + space (or end of line)
                                        text_amounts = re.findall(r'(?:\s|^)([\d,]+\.\d{2})(?:\s|$)', line_stripped)
                                        # Also check for amounts at the end of line after hex codes
                                        # Remove any hex-code-like patterns (long alphanumeric strings > 20 chars) first
                                        cleaned_line = re.sub(r'[a-f0-9]{20,}', '', line_stripped, flags=re.IGNORECASE)
                                        cleaned_amounts = re.findall(r'(?:\s|^)([\d,]+\.\d{2})(?:\s|$)', cleaned_line)
                                        
                                        # Use cleaned amounts if they exist and are fewer (more accurate)
                                        if cleaned_amounts and len(cleaned_amounts) <= len(text_amounts):
                                            text_amounts = cleaned_amounts
                                        
                                        if text_amounts:
                                            try:
                                                parsed_amounts = [float(a.replace(',', '')) for a in text_amounts[:2]]
                                                # Filter out unreasonable amounts and very small ones
                                                # Also filter out amounts that look like they're from hex codes (very large)
                                                parsed_amounts = [a for a in parsed_amounts if 0.01 < a < 10000]
                                                if len(parsed_amounts) >= 2:
                                                    pending_transaction['Deposits'] = parsed_amounts[0]
                                                    pending_transaction['Balance'] = parsed_amounts[-1]
                                                    break
                                                elif len(parsed_amounts) == 1:
                                                    pending_transaction['Deposits'] = parsed_amounts[0]
                                                    break
                                            except:
                                                pass
                                        break
                                
                                # If we found amounts above, we're done with this search
                                if pending_transaction.get('Deposits') or pending_transaction.get('Withdrawals'):
                                    break
                    
                    # Finalize transaction if we have amounts
                    if pending_transaction.get('Deposits') or pending_transaction.get('Withdrawals'):
                        transactions.append(pending_transaction)
                        pending_transaction = None
                        continue  # Skip processing this row as a new transaction
                    else:
                        # Still building description, continue to next row
                        continue
                
                # Check if this is a hex code or reference line that should be merged with previous transaction
                # Hex codes are long alphanumeric strings without spaces, or short reference codes
                is_hex_code = False
                is_ref_code = False
                if desc:
                    desc_stripped = desc.strip()
                    # Check for hex codes (long alphanumeric)
                    if re.match(r'^[a-f0-9]{20,}$', desc_stripped, re.IGNORECASE):
                        is_hex_code = True
                    # Check for reference codes (shorter codes like C1ASQqJgmHCm)
                    elif len(desc_stripped) >= 8 and len(desc_stripped) <= 20 and re.match(r'^[a-zA-Z0-9]+$', desc_stripped):
                        is_ref_code = True
                
                # If it's a hex code or reference code line - if we have a pending transaction, merge it
                # OR if description exists but no date, it might be continuation of previous transaction
                if pending_transaction:
                    # Add description to pending transaction - include everything
                    desc_clean = desc.strip()
                    if desc_clean and desc_clean.lower() not in ['', 'nan', 'none']:
                        pending_transaction['Description'] += ' ' + desc_clean
                    
                    # Check ALL columns for additional description parts (like EPIK has C1ASQqJgmHCm in col 2)
                    # Include EVERYTHING that could be part of the description
                    for col_idx in range(len(row)):
                        # Skip date column - we already have the date
                        if col_idx == table_date_col:
                            continue
                        
                        col_val = str(row.iloc[col_idx]).strip()
                        if not col_val or col_val.lower() in ['', 'nan', 'none']:
                            continue
                        
                        # If it's the description column, we already added it above
                        if col_idx == table_desc_col:
                            continue
                        
                        # Check if this column has an amount that we've already extracted
                        # Only skip if we've already extracted that amount
                        is_extracted_amount = False
                        if col_idx == table_debit_col:
                            # Only skip if this is the debit we extracted
                            debit_str_check = col_val
                            if debit and abs(float(debit_str_check.replace(',', '')) - debit) < 0.01:
                                is_extracted_amount = True
                        elif col_idx == table_credit_col:
                            credit_str_check = col_val
                            if credit and abs(float(credit_str_check.replace(',', '')) - credit) < 0.01:
                                is_extracted_amount = True
                        elif col_idx == table_balance_col:
                            balance_str_check = col_val
                            if balance and abs(float(balance_str_check.replace(',', '')) - balance) < 0.01:
                                is_extracted_amount = True
                        
                        # If it's not an extracted amount, include it in description
                        # Include EVERYTHING except extracted amounts - no filtering
                        if not is_extracted_amount:
                            pending_transaction['Description'] += ' ' + col_val
                    
                    # Extract amounts from proper columns if available
                    if credit:
                        pending_transaction['Deposits'] = credit
                    if debit:
                        pending_transaction['Withdrawals'] = debit
                    if balance:
                        pending_transaction['Balance'] = balance
                    
                    # Finalize the transaction if we have amounts
                    if pending_transaction.get('Deposits') or pending_transaction.get('Withdrawals'):
                        transactions.append(pending_transaction)
                        pending_transaction = None
                        continue
                
                # Also handle if it's a hex code or reference code but no pending transaction yet
                # (this shouldn't happen often, but just in case)
                if is_hex_code or is_ref_code:
                    # This is unexpected - skip for now
                    continue
                
                # Check for continuation page transaction lines (malformed dates, continuation of previous date)
                # These often appear on page 2+ and have malformed dates like "1177JJuunn"
                # Skip these - they're usually duplicates or misformatted continuation page entries
                if date_str and re.match(r'^\d{3,}', date_str):
                    # Malformed date (too many digits) - skip this row
                    continue
                
                # If description exists but no amounts, it might be first line of multi-line transaction
                if desc and desc.lower() not in ['', 'nan', 'none'] and not debit and not credit and not balance and not all_amounts:
                    # Check if next row might have amounts or be continuation
                    is_multiline = False
                    if i + 1 < len(transaction_table):
                        next_row = transaction_table.iloc[i + 1]
                        next_desc = str(next_row.iloc[table_desc_col]).strip() if table_desc_col < len(next_row) else ''
                        # If next row has description but no date, it's likely continuation
                        if next_desc and not re.match(r'^\d{1,2}\s*\w{3}', next_desc) and next_desc.lower() not in ['', 'nan', 'none']:
                            is_multiline = True
                    
                    if is_multiline:
                        pending_transaction = {
                            'Date': current_date.strftime('%Y-%m-%d'),
                            'Description': desc,
                            'Withdrawals': None,
                            'Deposits': None,
                            'Balance': None
                        }
                        continue
                
                # Skip if no amounts found and no description to build on
                if debit is None and credit is None and balance is None:
                    continue
                
                # If this row has amounts but looks like a hex code continuation, skip creating a new transaction
                # (it should have been merged with pending transaction above)
                if is_hex_code and (debit or credit or balance):
                    continue
                
                # If we have a balance, use it to determine debit/credit if not already set
                # This helps with continuation pages where the format might be unclear
                if balance and len(transactions) > 0 and transactions[-1].get('Balance'):
                    prev_balance = transactions[-1]['Balance']
                    balance_change = balance - prev_balance
                    
                    # If we don't have debit/credit but have balance change, infer it
                    if debit is None and credit is None:
                        if balance_change > 0:
                            credit = balance_change
                        elif balance_change < 0:
                            debit = abs(balance_change)
                    # If we have an amount but it doesn't match the balance change, correct it
                    elif credit and abs(credit - balance_change) > 0.01:
                        # Amount doesn't match balance change - might be wrong
                        # Try to correct based on balance change
                        if balance_change > 0:
                            credit = balance_change
                            debit = None
                        else:
                            debit = abs(balance_change)
                            credit = None
                    elif debit and abs(debit + balance_change) > 0.01:
                        # Debit amount doesn't match balance change
                        if balance_change < 0:
                            debit = abs(balance_change)
                            credit = None
                
                # Collect ALL description parts from ALL columns (not just description column)
                # This ensures we capture names like "Sarine Kassemdjian" that are in other columns
                # Also handles old format where description spans multiple columns
                all_desc_parts = []
                
                # Collect from ALL columns between date and first amount column
                # Amount columns are: debit, credit, balance
                amount_cols = [c for c in [table_debit_col, table_credit_col, table_balance_col] if c is not None]
                first_amount_col = min(amount_cols) if amount_cols else len(row)
                
                # Collect all non-amount, non-date columns
                for col_idx in range(len(row)):
                    # Skip date column
                    if col_idx == table_date_col:
                        continue
                    
                    # Skip amount columns
                    if col_idx in amount_cols:
                        continue
                    
                    col_val = str(row.iloc[col_idx]).strip()
                    if not col_val or col_val.lower() in ['', 'nan', 'none']:
                        continue
                    
                    # Additional check: if this looks like an amount (has decimal pattern), skip it
                    if re.match(r'^[\d,]+\.\d{2}$', col_val.replace('$', '').replace(',', '').strip()):
                        # This looks like an amount, skip it
                        continue
                    
                    # Add to description parts
                    all_desc_parts.append(col_val)
                
                # Combine all description parts, removing duplicates while preserving order
                seen = set()
                unique_parts = []
                for part in all_desc_parts:
                    if part not in seen:
                        seen.add(part)
                        unique_parts.append(part)
                
                full_description = ' '.join(unique_parts) if unique_parts else 'Transaction'
                
                transactions.append({
                    'Date': current_date.strftime('%Y-%m-%d'),
                    'Description': full_description,
                    'Withdrawals': debit if debit else None,
                    'Deposits': credit if credit else None,
                    'Balance': balance
                })
                
                # Reset pending transaction
                pending_transaction = None
    
    except Exception as e:
        print(f"Error extracting with Camelot: {e}")
        import traceback
        traceback.print_exc()
        return None, opening_balance, closing_balance, statement_year
    
    if not transactions:
        return None, opening_balance, closing_balance, statement_year
    
    df = pd.DataFrame(transactions)
    
    # Calculate running balance manually from opening balance, withdrawals, and deposits
    # When Balance column from PDF is available, use it to correct running balance
    if opening_balance is not None:
        running_balance = opening_balance
        running_balances = []
        has_balance_column = 'Balance' in df.columns and df['Balance'].notna().any()
        
        for idx, row in df.iterrows():
            # If this transaction has a Balance value from the PDF, use it
            # This is especially important for old format statements where balance is provided intermittently
            if has_balance_column and pd.notna(row.get('Balance')):
                actual_balance = float(row.get('Balance'))
                running_balance = actual_balance
                running_balances.append(running_balance)
            else:
                # Calculate running balance normally
                if pd.notna(row.get('Withdrawals')):
                    running_balance -= row['Withdrawals']
                if pd.notna(row.get('Deposits')):
                    running_balance += row['Deposits']
                running_balances.append(running_balance)
        
        df['Running_Balance'] = running_balances
    else:
        df['Running_Balance'] = None
    
    return df, opening_balance, closing_balance, statement_year

if __name__ == "__main__":
    # Test on a single file
    pdf_path = "data/RBC Chequing 3143 Jan 22, 2025 - Dec 22, 2025/2. Feb 2025.pdf"
    df, opening, closing, year = extract_rbc_chequing_statement(pdf_path)
    
    if df is not None:
        print(f"Extracted {len(df)} transactions")
        print(f"Opening: ${opening:,.2f}" if opening else "Opening: Not found")
        print(f"Closing: ${closing:,.2f}" if closing else "Closing: Not found")
        print(f"Year: {year}")
        print("\nAll transactions:")
        print(df.to_string())
        
        # Check balance match
        if 'Running_Balance' in df.columns and closing is not None:
            final_rb = df['Running_Balance'].iloc[-1]
            diff = abs(final_rb - closing)
            print(f"\nFinal Running Balance: ${final_rb:,.2f}")
            print(f"Closing Balance: ${closing:,.2f}")
            print(f"Difference: ${diff:,.2f}")
            if diff < 0.01:
                print("Balance matches!")
            else:
                print("Balance mismatch")
    else:
        print("Failed to extract transactions")
