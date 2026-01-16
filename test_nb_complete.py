#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete test script for NB Bank statement extraction (CAD and USD)
"""

import pdfplumber
import pandas as pd
import re
from datetime import datetime
from pathlib import Path

def extract_nb_statement(pdf_path: str):
    """
    Extract transactions from NB Bank statement (CAD or USD).
    
    Returns:
    - df: DataFrame with Date, Description, Withdrawals, Deposits, Balance, Running_Balance
    - opening_balance: float or None
    - closing_balance: float or None
    - statement_year: str or None
    """
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    currency = None
    
    print(f"\n{'='*80}")
    print(f"EXTRACTING NB STATEMENT: {Path(pdf_path).name}")
    print(f"{'='*80}\n")
    
    # Extract using pdfplumber to get tables
    with pdfplumber.open(pdf_path) as pdf:
        # Extract full text for metadata
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        # Extract statement period and year
        period_match = re.search(r'Period from\s+(\d{4})-(\d{2})-(\d{2})\s+to\s+(\d{4})-(\d{2})-(\d{2})', full_text)
        if period_match:
            start_year = int(period_match.group(1))
            end_year = int(period_match.group(4))
            statement_year = str(end_year)  # Use end year
            print(f"Statement period: {period_match.group(0)}")
            print(f"Statement year: {statement_year}")
        
        # Detect currency
        if 'CDN$' in full_text or '(CDN$)' in full_text or 'CURRENT ACCOUNT (CDN$)' in full_text:
            currency = 'CAD'
            print(f"Currency: CAD")
        elif 'USD$' in full_text or '(USD$)' in full_text or 'CURRENT ACCOUNT (USD$)' in full_text or 'U.S.$' in full_text:
            currency = 'USD'
            print(f"Currency: USD")
        
        # Extract tables from first page
        first_page = pdf.pages[0]
        tables = first_page.extract_tables()
        
        # Find transaction table (Table 2 based on exploration)
        transaction_table = None
        for table in tables:
            if len(table) > 0 and len(table[0]) >= 5:
                # Check if this is the transaction table (has MM, DD, DESCRIPTION, DEBIT, CREDIT, BALANCE)
                header_row = table[0]
                header_text = ' '.join([str(cell) if cell else '' for cell in header_row]).upper()
                if 'MM' in header_text and 'DD' in header_text and 'DESCRIPTION' in header_text:
                    transaction_table = table
                    break
        
        if not transaction_table:
            print("ERROR: Could not find transaction table")
            return pd.DataFrame(), None, None, statement_year
        
        print(f"\nFound transaction table with {len(transaction_table)} rows")
        
        # Parse transactions
        month_map = {
            1: '01', 2: '02', 3: '03', 4: '04', 5: '05', 6: '06',
            7: '07', 8: '08', 9: '09', 10: '10', 11: '11', 12: '12'
        }
        
        # Header row is first row: ['MM', 'DD', 'DESCRIPTION', 'DEBIT ($)', 'CREDIT ($)', 'BALANCE ($)']
        for row_idx in range(1, len(transaction_table)):
            row = transaction_table[row_idx]
            
            if not row or len(row) < 3:
                continue
            
            # Extract columns
            mm_str = str(row[0]).strip() if row[0] else ''
            dd_str = str(row[1]).strip() if row[1] else ''
            description = str(row[2]).strip() if len(row) > 2 and row[2] else ''
            debit_str = str(row[3]).strip() if len(row) > 3 and row[3] else ''
            credit_str = str(row[4]).strip() if len(row) > 4 and row[4] else ''
            balance_str = str(row[5]).strip() if len(row) > 5 and row[5] else ''
            
            # Check for previous balance (opening balance)
            if 'PREVIOUS BALANCE' in description.upper():
                if balance_str:
                    try:
                        opening_balance = float(balance_str.replace(',', '').replace('$', '').strip())
                        print(f"Opening balance: ${opening_balance:,.2f}")
                    except:
                        pass
                continue  # Don't add as transaction
            
            # Skip empty rows
            if not mm_str or not dd_str or not description:
                continue
            
            # Skip summary rows
            if 'NUMBER' in description.upper() or 'TRANSACTIONS' in description.upper() or 'TOTAL' in description.upper():
                continue
            
            # Parse date
            try:
                mm = int(mm_str)
                dd = int(dd_str)
                
                # Determine year - if month is 12, it might be from previous year if statement starts in January
                # For simplicity, use statement_year for all transactions (usually same year)
                year = int(statement_year) if statement_year else 2025
                
                # Handle year-end statements (Dec transactions might be from previous year)
                if mm == 12 and statement_year:
                    # If statement period starts in Jan, Dec transactions are from previous year
                    period_start_month = int(period_match.group(2)) if period_match else None
                    if period_start_month == 1:
                        year = int(statement_year) - 1
                
                full_date = datetime(year, mm, dd)
                date_str = full_date.strftime('%Y-%m-%d')
                
            except Exception as e:
                print(f"Warning: Could not parse date from '{mm_str}/{dd_str}': {e}")
                continue
            
            # Parse amounts
            withdrawal = None
            deposit = None
            balance = None
            
            if debit_str:
                try:
                    withdrawal = float(debit_str.replace(',', '').replace('$', '').strip())
                except:
                    pass
            
            if credit_str:
                try:
                    deposit = float(credit_str.replace(',', '').replace('$', '').strip())
                except:
                    pass
            
            if balance_str:
                try:
                    balance = float(balance_str.replace(',', '').replace('$', '').strip())
                except:
                    pass
            
            # Closing balance is the last balance
            if balance is not None:
                closing_balance = balance
            
            transactions.append({
                'Date': date_str,
                'Description': description,
                'Withdrawals': withdrawal if withdrawal else None,
                'Deposits': deposit if deposit else None,
                'Balance': balance,
            })
        
        print(f"\nExtracted {len(transactions)} transactions")
    
    # Create DataFrame
    if transactions:
        df = pd.DataFrame(transactions)
        
        # Sort by date
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
        # Fill None values with 0
        df['Withdrawals'] = df['Withdrawals'].fillna(0)
        df['Deposits'] = df['Deposits'].fillna(0)
        
        # Calculate running balance
        if opening_balance is not None:
            df['Running_Balance'] = opening_balance + (df['Deposits'] - df['Withdrawals']).cumsum()
        else:
            # Calculate from first balance if available
            if 'Balance' in df.columns and df['Balance'].notna().any():
                # Reverse engineer opening balance from first transaction
                first_balance = df['Balance'].iloc[0]
                first_net = df['Deposits'].iloc[0] - df['Withdrawals'].iloc[0]
                opening_balance = first_balance - first_net
                df['Running_Balance'] = opening_balance + (df['Deposits'] - df['Withdrawals']).cumsum()
                print(f"Inferred opening balance: ${opening_balance:,.2f}")
            else:
                df['Running_Balance'] = (df['Deposits'] - df['Withdrawals']).cumsum()
        
        # Convert Date back to string format
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    else:
        df = pd.DataFrame()
    
    if closing_balance:
        print(f"Closing balance: ${closing_balance:,.2f}")
    
    return df, opening_balance, closing_balance, statement_year


if __name__ == "__main__":
    import sys
    import io
    # Fix encoding for Windows (only when run as script)
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # Test on first file from CAD folder
    cad_dir = Path("data/NB-CAD acount 8528")
    cad_files = sorted(cad_dir.glob("*.pdf"))
    
    if cad_files:
        print(f"Testing NB CAD file: {cad_files[0].name}")
        df, opening, closing, year = extract_nb_statement(str(cad_files[0]))
        
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
        print(f"No PDF files found in {cad_dir}")
