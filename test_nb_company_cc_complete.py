#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete test script for NB Company Credit Card statement extraction
"""

import pdfplumber
import pandas as pd
import re
import camelot
from datetime import datetime
from pathlib import Path

def extract_nb_company_cc_statement(pdf_path: str):
    """
    Extract transactions from NB Company Credit Card statement.
    
    Returns:
    - df: DataFrame with Date, Description, Amount, Running_Balance
    - opening_balance: float or None
    - closing_balance: float or None
    - statement_year: str or None
    """
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_start_year = None
    statement_end_year = None
    
    print(f"\n{'='*80}")
    print(f"EXTRACTING NB COMPANY CREDIT CARD: {Path(pdf_path).name}")
    print(f"{'='*80}\n")
    
    # Extract text for statement period
    with pdfplumber.open(pdf_path) as pdf:
        # Get full text to find statement period
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        # Look for statement period - format appears to be in filename: "Dec 8 2024 - Jan 2 2025"
        # Try filename first (more reliable)
        filename = Path(pdf_path).stem
        # Pattern: "1. Dec 8 2024 - Jan 2 2025" or "Dec 8 2024 - Jan 2 2025"
        period_match = re.search(r'(?:^\d+\.\s+)?([A-Z][a-z]+)\s+\d{1,2}\s+(\d{4})\s+-\s+([A-Z][a-z]+)\s+\d{1,2}\s+(\d{4})', filename, re.IGNORECASE)
        if period_match:
            statement_start_year = period_match.group(2)
            statement_end_year = period_match.group(4)
        else:
            # Try in text like "Dec 08 2024 - Jan 02 2025"
            period_match = re.search(r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\s*-\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})', full_text)
            if period_match:
                period_text = period_match.group(0)
                year_matches = re.findall(r'\d{4}', period_text)
                if year_matches:
                    statement_start_year = year_matches[0]
                    statement_end_year = year_matches[-1] if len(year_matches) > 1 else year_matches[0]
        
        if not statement_start_year:
            statement_start_year = "2024"
            statement_end_year = "2025"
        
        print(f"Statement period: {statement_start_year} to {statement_end_year}")
        
        # Extract opening balance - appears as "5258 819000 341074 001 $40.43" above transaction table
        # Can also be negative: "5258 819000 341074 001 $40.43-" 
        # Pattern: account numbers + sequence (001/002) + $ + amount (with optional -)
        opening_balance_match = re.search(r'\d+\s+\$\s*([\d,]+\.\d{2})(-?)(?=\s*\d{2}\s+\d{2}\s+[A-Z0-9])', full_text)
        # Also try the more specific pattern: sequence number + $ + amount
        if not opening_balance_match:
            opening_balance_match = re.search(r'\b\d{3}\s+\$\s*([\d,]+\.\d{2})(-?)(?=\s*\d{2}\s+\d{2})', full_text)
        # Also try the account number pattern: "5258 819000 341074 001 $40.43" or "5258 819000 341074 001 $40.43-"
        if not opening_balance_match:
            opening_balance_match = re.search(r'\d{4}\s+\d{6}\s+\d{6}\s+\d{3}\s+\$\s*([\d,]+\.\d{2})(-?)', full_text)
        if opening_balance_match:
            try:
                amount_str = opening_balance_match.group(1).replace(',', '')
                has_dash = opening_balance_match.group(2) == '-'
                opening_balance = float(amount_str)
                if has_dash:
                    opening_balance = -opening_balance
                print(f"Opening balance: ${opening_balance:,.2f}")
            except:
                pass
        
        # Extract closing balance from top line: 
        # Format 1: "25 01 02 $130.61 $130.61 2025 01 23" (same amount twice = closing)
        # Format 2: "25 03 03 $162.23- $0.00 2025 03 24" (first amount with dash is closing, negative)
        # Check if first amount has a dash (negative indicator)
        top_line_match = re.search(r'\d{2}\s+\d{2}\s+\d{2}\s+\$([\d,]+\.\d{2})(-?)\s+\$([\d,]+\.\d{2})', full_text)
        if top_line_match:
            try:
                first_amt_str = top_line_match.group(1).replace(',', '')
                has_dash = top_line_match.group(2) == '-'
                second_amt_str = top_line_match.group(3).replace(',', '')
                first_amt = float(first_amt_str)
                second_amt = float(second_amt_str)
                
                # If first amount has a dash, it's the closing balance (negative)
                if has_dash:
                    closing_balance = -first_amt
                # If both amounts are the same, that's the closing balance
                elif abs(first_amt - second_amt) < 0.01:
                    closing_balance = first_amt
                # Otherwise, use the first amount as closing balance
                else:
                    closing_balance = first_amt
                print(f"Closing balance (from top): ${closing_balance:,.2f}")
            except Exception as e:
                print(f"DEBUG: Exception in top_line_match: {e}")
                pass
        
        # Also check bottom line for closing balance: "19,869 19,869 2025/01/23 0.00 130.61"
        if closing_balance is None:
            # Try pattern with date before balance (last number in line)
            bottom_match = re.search(r'(\d{4}/\d{2}/\d{2})\s+[\d,]+\.[\d]{2}\s+([\d,]+\.\d{2})\s*$', full_text, re.MULTILINE)
            if bottom_match:
                try:
                    closing_balance = float(bottom_match.group(2).replace(',', ''))
                    print(f"Closing balance (from bottom): ${closing_balance:,.2f}")
                except:
                    pass
        
        # Try another pattern: look for "NEW BALANCE" or similar
        if closing_balance is None:
            new_balance_match = re.search(r'(?:NEW\s+)?BALANCE[:\s]+\$?([\d,]+\.\d{2})', full_text, re.IGNORECASE)
            if new_balance_match:
                try:
                    closing_balance = float(new_balance_match.group(1).replace(',', ''))
                    print(f"Closing balance (from NEW BALANCE): ${closing_balance:,.2f}")
                except:
                    pass
    
    # Extract transactions using Camelot
    all_tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # From Camelot output, Table 1 has transactions in this format:
    # Column 0: "12 20  I355298928" (trans date MM DD + reference)
    # Column 1: "12 23 PAYMENT VIA ELECTRONIC TRANSFER" (post date MM DD + description start)
    # Column 2: "40.43-" (amount, or description continuation + amount)
    
    for table_idx, table in enumerate(all_tables):
        df = table.df.fillna('')
        
        # Process each row
        for idx in range(len(df)):
            row = df.iloc[idx]
            row_list = [str(cell).strip() for cell in row.tolist()]
            row_text = ' '.join(row_list).upper()
            
            # Skip summary rows
            if any(keyword in row_text for keyword in ['SUMMARY FOR', 'CREDIT LIMIT', 'MONTHLY TRANSACTIONS', 'TOTAL', 'NUMBER', 'POINTS', 'EXPENSE LIMIT', 'A LA CARTE', 'PREVIOUS POINTS', 'POINTS REDEEMED', 'POINTS EARNED', 'NEW POINTS']):
                continue
            
            # Skip empty rows or header rows
            if len(row_list) < 3 or not any(row_list):
                continue
            
            # Column 0 contains the entire transaction
            # Format: "12 20  I355298928  12 23 PAYMENT VIA ELECTRONIC TRANSFER              40.43-"
            # Or: "12 08  U372678006  12 09 RANI CHETTINAD         WATERLOO      ON      64.98"
            # Pattern: MM DD [REF] MM DD [DESCRIPTION] [AMOUNT]
            
            col0 = row_list[0]
            
            # Match transaction date (MM DD) at start
            trans_date_match = re.match(r'^(\d{1,2})\s+(\d{1,2})', col0)
            if not trans_date_match:
                continue
            
            try:
                trans_mm = int(trans_date_match.group(1))
                trans_dd = int(trans_date_match.group(2))
                
                if not (1 <= trans_mm <= 12 and 1 <= trans_dd <= 31):
                    continue
            except:
                continue
            
            # Find post date (MM DD) after reference
            # Skip past transaction date and reference
            rest_after_trans_date = col0[trans_date_match.end():].strip()
            
            # Find post date pattern (MM DD) - should appear after reference
            # Description can start with special chars like *, so allow those after space
            # Make sure we don't match inside reference numbers - look for space before and after
            post_date_match = re.search(r'\s+(\d{1,2})\s+(\d{1,2})(?=\s+[A-Z*])', rest_after_trans_date)
            if not post_date_match:
                continue
            
            try:
                post_mm = int(post_date_match.group(1))
                post_dd = int(post_date_match.group(2))
                
                if not (1 <= post_mm <= 12 and 1 <= post_dd <= 31):
                    continue
            except:
                continue
            
            # Extract description and amount
            # Everything after post date is description + amount
            desc_and_amount = rest_after_trans_date[post_date_match.end():].strip()
            
            # Find amount at the end (pattern: number.number- or number.number)
            amount_match = re.search(r'([\d,]+\.\d{2})-?$', desc_and_amount)
            if not amount_match:
                continue
            
            amount_str = amount_match.group(1)
            description = desc_and_amount[:amount_match.start()].strip()
            
            if not description:
                continue
            
            # Check if amount has negative sign
            is_negative = desc_and_amount.endswith('-')
            
            # Parse amount
            try:
                amount = float(amount_str.replace(',', ''))
                if is_negative:
                    amount = -amount
            except:
                continue
            
            # Determine year for transaction date (use TRANS date, not post date)
            start_year = int(statement_start_year)
            end_year = int(statement_end_year)
            
            # If statement spans two years, use start year for Dec, end year for Jan
            if start_year != end_year:
                if trans_mm >= 10:  # Oct, Nov, Dec
                    trans_year = start_year
                else:  # Jan, Feb, etc.
                    trans_year = end_year
            else:
                trans_year = end_year
            
            try:
                trans_date = datetime(trans_year, trans_mm, trans_dd)
                date_str = trans_date.strftime('%Y-%m-%d')
            except:
                continue
            
            transactions.append({
                'Date': date_str,
                'Description': description,
                'Amount': amount
            })
    
    # Create DataFrame
    if transactions:
        df = pd.DataFrame(transactions)
        df = df.sort_values('Date').reset_index(drop=True)
        
        # Calculate running balance
        if opening_balance is not None:
            df['Running_Balance'] = opening_balance + df['Amount'].cumsum()
        else:
            df['Running_Balance'] = df['Amount'].cumsum()
    else:
        df = pd.DataFrame()
    
    statement_year = statement_end_year if statement_end_year else statement_start_year
    
    print(f"\nExtracted {len(df)} transactions")
    
    return df, opening_balance, closing_balance, statement_year


if __name__ == "__main__":
    import sys
    import io
    # Fix encoding for Windows (only when run as script)
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # Test on first file
    pdf_dir = Path("data/NB- Company Credit Card 1074")
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    
    if pdf_files:
        print(f"Testing NB Company Credit Card: {pdf_files[0].name}")
        df, opening, closing, year = extract_nb_company_cc_statement(str(pdf_files[0]))
        
        print(f"\n{'='*80}")
        print("RESULTS")
        print(f"{'='*80}")
        print(f"Opening Balance: ${opening:,.2f}" if opening else "Opening Balance: None")
        print(f"Closing Balance: ${closing:,.2f}" if closing else "Closing Balance: None")
        print(f"Statement Year: {year}")
        print(f"\nExtracted {len(df)} transactions:\n")
        
        if not df.empty:
            print(df.to_string())
            
            # Check if running balance matches closing balance
            if closing and 'Running_Balance' in df.columns and len(df) > 0:
                final_rb = df['Running_Balance'].iloc[-1]
                diff = abs(final_rb - closing)
                print(f"\nRunning Balance Check:")
                print(f"  Final Running Balance: ${final_rb:,.2f}")
                print(f"  Closing Balance: ${closing:,.2f}")
                print(f"  Difference: ${diff:,.2f}")
                if diff < 0.01:
                    print(f"  ✅ Balance matches!")
                else:
                    print(f"  ⚠️  Balance difference exceeds tolerance")
    else:
        print(f"No PDF files found in {pdf_dir}")
