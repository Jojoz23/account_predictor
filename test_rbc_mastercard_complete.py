#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBC Mastercard Statement Extractor
Extracts transactions from RBC Mastercard PDF statements
"""

import camelot
import pdfplumber
import pandas as pd
import re
from datetime import datetime
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except:
        pass


def extract_rbc_mastercard_statement(pdf_path):
    """
    Extract transactions from RBC Mastercard statement
    
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
    # Handle formats like "STATEMENTFROMDEC11,2024TOJAN10,2025" (no spaces)
    # Or "STATEMENT FROM FEB 11 TO MAR 10, 2025" (with spaces)
    period_match = re.search(r'STATEMENT\s*FROM\s*([A-Za-z]+)\s*(\d{1,2})(?:,\s*(\d{4}))?\s*TO\s*([A-Za-z]+)\s*(\d{1,2})(?:,\s*(\d{4}))?', full_text, re.IGNORECASE)
    statement_start_year = None
    statement_end_year = None
    statement_start_month = None
    statement_end_month = None
    
    if period_match:
        start_month_name = period_match.group(1)
        start_day = int(period_match.group(2))
        # Year might be in group 3 or we need to infer from end year
        if period_match.group(3):
            statement_start_year = int(period_match.group(3))
        end_month_name = period_match.group(4)
        end_day = int(period_match.group(5))
        if period_match.group(6):
            statement_end_year = int(period_match.group(6))
        # If start year not provided, infer from end year
        if not statement_start_year and statement_end_year:
            # If end month is before start month, start year is previous year
            month_map_temp = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            start_month_num = month_map_temp.get(start_month_name.lower(), 1)
            end_month_num = month_map_temp.get(end_month_name.lower(), 1)
            if end_month_num < start_month_num:
                statement_start_year = statement_end_year - 1
            else:
                statement_start_year = statement_end_year
        
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
    
    # Extract opening balance (Previous Statement Balance)
    # Look for the first occurrence (sometimes there are multiple)
    # Handle negative balances (e.g., "-$15.87" or "$15.87-")
    opening_patterns = [
        r'PREVIOUS\s*STATEMENT\s*BALANCE\s*(-?\$?)([\d,]+\.?\d*)',
        r'PREVIOUS\s*BALANCE\s*(-?\$?)([\d,]+\.?\d*)',
    ]
    for pattern in opening_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                sign_part = match.group(1)  # Could be "-$", "$", or "-"
                value_str = match.group(2).replace(',', '')
                
                # Check if negative (either "-$" or "-" in sign_part, or check after the amount)
                is_negative = '-' in sign_part
                if not is_negative:
                    # Check if there's a dash after the amount (e.g., "$15.87-")
                    match_end = match.end()
                    if match_end < len(full_text) and full_text[match_end:match_end+1] == '-':
                        is_negative = True
                
                value = float(value_str)
                opening_balance = -value if is_negative else value
                break
            except:
                continue
    
    # For December file, if no opening balance found, try calculating from closing - transactions
    # But we'll handle this after transaction extraction
    
    # Extract closing balance (New Balance)
    closing_patterns = [
        r'NEW\s*BALANCE\s*\$?([\d,]+\.?\d*)',
        r'CLOSING\s*BALANCE\s*\$?([\d,]+\.?\d*)',
    ]
    for pattern in closing_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                closing_balance = float(match.group(1).replace(',', ''))
                break
            except:
                continue
    
    # Extract transactions using Camelot with stream flavor
    try:
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        
        # Find the main transaction table (usually first table)
        # Find ALL transaction tables (some PDFs have multiple tables with duplicates)
        transaction_tables = []
        
        for table in tables:
            df = table.df
            header_row_idx = None
            
            # Look for transaction header - check multiple rows since header spans rows 8-10
            for row_idx in range(min(15, len(df))):
                row_text = ' '.join(df.iloc[row_idx].astype(str)).upper()
                # Check for "TRANSACTION POSTING" or "ACTIVITY DESCRIPTION" or "DATE DATE"
                if ('TRANSACTION' in row_text and 'POSTING' in row_text) or \
                   ('ACTIVITY' in row_text and 'DESCRIPTION' in row_text) or \
                   (row_idx + 1 < len(df) and 'DATE' in row_text and 'DATE' in ' '.join(df.iloc[row_idx + 1].astype(str)).upper()):
                    # Header starts around row 8-10, find the row with "ACTIVITY DESCRIPTION"
                    for check_row in range(max(0, row_idx - 2), min(row_idx + 3, len(df))):
                        check_text = ' '.join(df.iloc[check_row].astype(str)).upper()
                        if 'ACTIVITY' in check_text and 'DESCRIPTION' in check_text:
                            header_row_idx = check_row
                            break
                    if header_row_idx is None:
                        header_row_idx = row_idx
                    
                    transaction_tables.append((df, header_row_idx))
                    break
            
            # If no header found, check if table has transaction-like rows (dates + amounts)
            # This handles tables that start directly with transactions without headers
            if header_row_idx is None:
                transaction_count = 0
                for row_idx in range(min(20, len(df))):
                    row = df.iloc[row_idx]
                    col0 = str(row.iloc[0]).strip() if len(row) > 0 else ''
                    # Check if first column has a date pattern
                    if re.match(r'^[A-Z]{3}\s+\d{1,2}', col0):
                        # Check if any column has an amount
                        for col_idx in range(len(row)):
                            cell = str(row.iloc[col_idx])
                            if re.search(r'\$[\d,]+\.\d{2}', cell):
                                transaction_count += 1
                                break
                
                # If we found 3+ transaction-like rows, treat it as a transaction table
                if transaction_count >= 3:
                    # Start from row 0 (no header)
                    transaction_tables.append((df, -1))
        
        if not transaction_tables:
            print("Could not find transaction table")
            return None, opening_balance, closing_balance, statement_year
        
        # Process transactions starting after header
        month_map_tx = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        # Process ALL tables
        for transaction_table, header_row_idx in transaction_tables:
            # Determine table format based on number of columns
            num_cols = len(transaction_table.columns)
            
            # Dynamically detect column positions for dates, description, and amount
            # Check header row to find where "ACTIVITY DESCRIPTION" and "AMOUNT" are
            desc_col_idx = None
            amount_col_idx = None
            
            for check_row in range(max(0, header_row_idx - 2), min(header_row_idx + 3, len(transaction_table))):
                row = transaction_table.iloc[check_row]
                for col_idx in range(len(row)):
                    cell_text = str(row.iloc[col_idx]).upper().replace(' ', '')
                    if 'ACTIVITY' in cell_text and 'DESCRIPTION' in cell_text:
                        desc_col_idx = col_idx
                    if 'AMOUNT' in cell_text:
                        amount_col_idx = col_idx
                if desc_col_idx is not None and amount_col_idx is not None:
                    break
            
            # If not found, try default positions based on column count
            if desc_col_idx is None:
                desc_col_idx = 2 if num_cols >= 5 else 0
            if amount_col_idx is None:
                amount_col_idx = 3 if num_cols >= 5 else 1
            
            is_multi_column_format = num_cols >= 5
            
            current_date = None
            
            # Determine start row - if header_row_idx is -1, start from 0 (no header)
            start_row = 0 if header_row_idx == -1 else header_row_idx + 2
            
            for i in range(start_row, len(transaction_table)):
                row = transaction_table.iloc[i]
                
                # Skip empty rows
                if row.isna().all() or (row.astype(str).str.strip() == '').all():
                    continue
                
                # Handle different table formats
                if is_multi_column_format:
                    # Multi-column format: dates in Col 0 and Col 1, description and amount vary
                    trans_date_str = str(row.iloc[0]).strip() if len(row) > 0 else ''
                    desc_col = str(row.iloc[desc_col_idx]).strip() if len(row) > desc_col_idx else ''
                    amount_str = str(row.iloc[amount_col_idx]).strip() if len(row) > amount_col_idx else ''
                    
                    # Check if transaction date column has a date
                    date_match = re.match(r'^([A-Z]{3})\s+(\d{1,2})', trans_date_str)
                    if not date_match:
                        continue
                    
                    month_abbr = date_match.group(1).capitalize()
                    day = int(date_match.group(2))
                    month = month_map_tx.get(month_abbr, 1)
                    
                    # Determine correct year
                    transaction_year = statement_year
                    if statement_start_year is not None and statement_start_year != statement_end_year:
                        if month == statement_start_month:
                            transaction_year = statement_start_year
                        elif month == statement_end_month:
                            transaction_year = statement_end_year
                        elif month < statement_start_month:
                            transaction_year = statement_start_year
                        elif month > statement_end_month:
                            transaction_year = statement_end_year
                    
                    try:
                        current_date = datetime(transaction_year, month, day)
                    except:
                        continue
                    
                    # If description column is empty, check adjacent columns (header might be offset)
                    if not desc_col or desc_col.lower() in ['', 'nan', 'none']:
                        # Check column before (desc_col_idx - 1)
                        if desc_col_idx > 0:
                            prev_col = str(row.iloc[desc_col_idx - 1]).strip() if len(row) > desc_col_idx - 1 else ''
                            if prev_col and prev_col.lower() not in ['', 'nan', 'none'] and not re.match(r'^[A-Z]{3}\s+\d{1,2}', prev_col):
                                desc_col = prev_col
                        # Check column after (desc_col_idx + 1) if still empty
                        if (not desc_col or desc_col.lower() in ['', 'nan', 'none']) and desc_col_idx + 1 < len(row):
                            next_col = str(row.iloc[desc_col_idx + 1]).strip() if len(row) > desc_col_idx + 1 else ''
                            if next_col and next_col.lower() not in ['', 'nan', 'none'] and not re.match(r'^[A-Z]{3}\s+\d{1,2}', next_col) and '$' not in next_col:
                                desc_col = next_col
                    
                    description = desc_col if desc_col and desc_col.lower() not in ['', 'nan', 'none'] else 'Transaction'
                    
                else:
                    # Format 1: 3-column format
                    # Col 0: Dates + Description, Col 1: Amount
                    col0 = str(row.iloc[0]).strip() if len(row) > 0 else ''
                    amount_str = str(row.iloc[1]).strip() if len(row) > 1 else ''
                    
                    if not col0:
                        continue
                    
                    # Check if this is a transaction row (starts with date like "DEC 23")
                    date_match = re.match(r'^([A-Z]{3})\s+(\d{1,2})', col0)
                    if not date_match:
                        continue
                    
                    month_abbr = date_match.group(1).capitalize()
                    day = int(date_match.group(2))
                    month = month_map_tx.get(month_abbr, 1)
                    
                    # Determine correct year
                    transaction_year = statement_year
                    if statement_start_year is not None and statement_start_year != statement_end_year:
                        if month == statement_start_month:
                            transaction_year = statement_start_year
                        elif month == statement_end_month:
                            transaction_year = statement_end_year
                        elif month < statement_start_month:
                            transaction_year = statement_start_year
                        elif month > statement_end_month:
                            transaction_year = statement_end_year
                    
                    try:
                        current_date = datetime(transaction_year, month, day)
                    except:
                        continue
                    
                    # Extract description from column 0
                    # Format: "DEC 23\nDEC 24\nPAYMENT - THANK YOU / PAIEMENT - MERCI"
                    # Sometimes dates appear multiple times, so we need to clean them up
                    lines = col0.split('\n')
                    description_parts = []
                    seen_dates = set()
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        # Skip lines that are just dates (e.g., "DEC 23", "DEC 24")
                        # Also skip if it's a date we've already seen
                        date_check = re.match(r'^([A-Z]{3})\s+(\d{1,2})$', line)
                        if date_check:
                            date_key = date_check.group(1) + date_check.group(2)
                            if date_key not in seen_dates:
                                seen_dates.add(date_key)
                            continue
                        # Skip if line contains only dates separated by newlines
                        if re.match(r'^([A-Z]{3}\s+\d{1,2}\s*)+$', line):
                            continue
                        description_parts.append(line)
                    
                    description = ' '.join(description_parts) if description_parts else 'Transaction'
                    # Clean up any remaining date patterns
                    description = re.sub(r'\b[A-Z]{3}\s+\d{1,2}\s+', '', description).strip()
                    if not description:
                        description = 'Transaction'
                
                # Extract amount (same for both formats)
                amount = None
                if amount_str and amount_str.lower() not in ['', 'nan', 'none']:
                    amount_match = re.search(r'-?\$?([\d,]+\.\d{2})', amount_str)
                    if amount_match:
                        try:
                            is_negative = '-' in amount_str or amount_str.startswith('-')
                            value = float(amount_match.group(1).replace(',', ''))
                            amount = -value if is_negative else value
                        except:
                            pass
                
                if amount is None:
                    continue
                
                # Check next row for reference numbers (long numeric strings)
                reference = None
                if i + 1 < len(transaction_table):
                    next_row = transaction_table.iloc[i + 1]
                    # Check in description column
                    if is_multi_column_format:
                        next_ref = str(next_row.iloc[desc_col_idx]).strip() if len(next_row) > desc_col_idx else ''
                    else:
                        next_ref = str(next_row.iloc[0]).strip() if len(next_row) > 0 else ''
                    
                    if next_ref and re.match(r'^\d{15,}$', next_ref):
                        reference = next_ref
                        description = f"{description} {reference}".strip()
                
                transactions.append({
                    'Date': current_date.strftime('%Y-%m-%d'),
                    'Description': description,
                    'Amount': amount,
                    'Balance': None
                })
        # Remove duplicate transactions (same date, description, and amount)
        # For deduplication, remove reference numbers (long numeric strings) from description
        seen = set()
        unique_transactions = []
        for tx in transactions:
            # Clean description for comparison - remove reference numbers (15+ digit numbers)
            desc_clean = re.sub(r'\s+\d{15,}', '', tx['Description'])
            # Create a key for deduplication (date, cleaned description, amount)
            key = (tx['Date'], desc_clean[:50], tx['Amount'])
            if key not in seen:
                seen.add(key)
                unique_transactions.append(tx)
            else:
                print(f"Removing duplicate transaction: {tx['Date']} {tx['Description'][:50]} ${tx['Amount']:.2f}")
        transactions = unique_transactions
        
        # Sort transactions by date before calculating running balance
        transactions.sort(key=lambda tx: tx['Date'])
        
        # Calculate running balance
        if opening_balance is not None:
            running_balance = opening_balance
            for transaction in transactions:
                running_balance += transaction['Amount']  # Amount can be negative (credits)
                transaction['Balance'] = running_balance
        else:
            # If no opening balance, calculate from transactions backwards
            running_balance = closing_balance if closing_balance is not None else 0
            for transaction in reversed(transactions):
                transaction['Balance'] = running_balance
                running_balance -= transaction['Amount']
    
    except Exception as e:
        print(f"Error extracting with Camelot: {e}")
        import traceback
        traceback.print_exc()
        return None, opening_balance, closing_balance, statement_year
    
    if not transactions:
        return None, opening_balance, closing_balance, statement_year
    
    df = pd.DataFrame(transactions)
    
    # Add Running_Balance column (same as Balance for credit cards)
    df['Running_Balance'] = df['Balance'] if 'Balance' in df.columns else None
    
    return df, opening_balance, closing_balance, statement_year


if __name__ == "__main__":
    # Test on a single file
    pdf_path = "data/RBC Mastercard 2364 Jan 10, 2025 - Dec 10, 2025/1. Jan 2025.pdf"
    df, opening, closing, year = extract_rbc_mastercard_statement(pdf_path)
    
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
