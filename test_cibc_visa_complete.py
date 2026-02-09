#!/usr/bin/env python3
"""
CIBC Visa Credit Card Statement Extraction Script
Extracts transactions from CIBC Visa PDFs using camelot
"""

import pandas as pd
import re
import camelot
from datetime import datetime
from pathlib import Path

def extract_cibc_visa_statement(pdf_path: str):
    """
    Extract CIBC Visa statement
    
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
    
    # Step 1: Extract statement period and year
    tables_stream = camelot.read_pdf(pdf_path, pages="1", flavor="stream")
    
    if len(tables_stream) > 0:
        table1 = tables_stream[0].df.fillna('')
        for idx in range(min(20, len(table1))):
            row = table1.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            
            # Look for statement period: "December 26, 2024 to January 25, 2025" or "October 26 to November 25, 2025"
            period_match = re.search(
                r'([A-Z][a-z]+)\s+\d{1,2}(?:,\s*(\d{4}))?\s+to\s+([A-Z][a-z]+)\s+\d{1,2}(?:,\s*(\d{4}))?',
                row_text,
                re.IGNORECASE
            )
            if period_match:
                start_month = period_match.group(1)
                start_year = period_match.group(2)
                end_month = period_match.group(3)
                end_year = period_match.group(4)
                
                # If year is in the period, use it
                if end_year:
                    statement_end_year = end_year
                    statement_start_year = start_year if start_year else end_year
                elif start_year:
                    statement_start_year = start_year
                    statement_end_year = start_year
                break
    
    # If no year found, try to extract from statement date
    if not statement_start_year:
        for idx in range(min(20, len(table1))):
            row = table1.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            
            # Look for statement date: "January 25, 2025"
            date_match = re.search(r'([A-Z][a-z]+)\s+\d{1,2},\s+(\d{4})', row_text)
            if date_match:
                statement_end_year = date_match.group(2)
                statement_start_year = date_match.group(2)
                break
    
    if not statement_start_year:
        statement_start_year = "2025"
        statement_end_year = "2025"
    
    # Step 2: Extract opening and closing balances
    all_tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    
    for table_idx, table in enumerate(all_tables):
        df = table.df.fillna('')
        
        for idx in range(len(df)):
            row = df.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            row_text_upper = row_text.upper()
            
            # Previous balance
            if 'PREVIOUS BALANCE' in row_text_upper and opening_balance is None:
                amount_match = re.search(r'\$?([\d,]+\.\d{2})', row_text)
                if amount_match:
                    try:
                        opening_balance = float(amount_match.group(1).replace(',', ''))
                    except:
                        pass
            
            # Total balance / New balance
            if ('TOTAL BALANCE' in row_text_upper or 'NEW BALANCE' in row_text_upper) and closing_balance is None:
                amount_match = re.search(r'=\s*\$?([\d,]+\.\d{2})', row_text)
                if not amount_match:
                    amount_match = re.search(r'\$?([\d,]+\.\d{2})', row_text)
                if amount_match:
                    try:
                        closing_balance = float(amount_match.group(1).replace(',', ''))
                    except:
                        pass
    
    # Step 3: Extract transactions from Table 3 (page 2)
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # Find transaction table (typically Table 3 on page 2)
    transaction_table = None
    for table_idx, table in enumerate(all_tables):
        if table.page == 2:  # Transactions are on page 2
            df = table.df.fillna('')
            
            # Check if this is the transaction table
            for idx in range(min(5, len(df))):
                row_text = ' '.join([str(cell) for cell in df.iloc[idx].tolist()])
                if 'TRANSACTIONS' in row_text.upper() or 'YOUR PAYMENTS' in row_text.upper():
                    transaction_table = table
                    break
            
            if transaction_table:
                break
    
    if not transaction_table:
        # Fallback: use table 2 or 3 (indices 1 or 2) if on page 2
        for table_idx in [1, 2]:
            if table_idx < len(all_tables) and all_tables[table_idx].page == 2:
                transaction_table = all_tables[table_idx]
                break
    
    if transaction_table:
        df = transaction_table.df.fillna('')
        
        # Find sections: "Your payments" and "Your new charges and credits"
        payments_start = None
        charges_start = None
        
        for idx in range(len(df)):
            row_text = ' '.join([str(cell) for cell in df.iloc[idx].tolist()]).upper()
            
            if 'YOUR PAYMENTS' in row_text:
                payments_start = idx
            if 'YOUR NEW CHARGES' in row_text or 'YOUR NEW CHARGES AND CREDITS' in row_text:
                charges_start = idx
                break
        
        # Extract payments section
        if payments_start is not None:
            # Find header row (row 3 has "date\ndate Description Amount($)")
            header_row = None
            for idx in range(payments_start + 1, min(payments_start + 5, len(df))):
                row_text = ' '.join([str(cell) for cell in df.iloc[idx].tolist()]).upper()
                if 'DATE' in row_text and 'AMOUNT' in row_text:
                    header_row = idx
                    break
            
            if header_row:
                # Parse payment transactions
                for idx in range(header_row + 1, charges_start if charges_start else len(df)):
                    row = df.iloc[idx]
                    row_list = [str(cell).strip() for cell in row.tolist()]
                    row_text = ' '.join(row_list).upper()
                    
                    print(f"DEBUG: Processing row {idx}: {row_list}")
                    
                    # Stop at total or section end
                    if 'TOTAL PAYMENTS' in row_text:
                        print(f"DEBUG: Stopping at 'Total payments'")
                        break
                    if not any(row_list):
                        continue
                    
                    # Skip header rows
                    if 'TRANS' in row_text and 'DATE' in row_text:
                        print(f"DEBUG: Skipping header row")
                        continue
                    
                    # Parse transaction: Trans date, Post date, Description, Amount
                    if len(row_list) >= 3:
                        # Dates can be in two formats:
                        # Format 1: Combined in column 0 with newline: "Dec 25\nDec 30"
                        # Format 2: Separate columns: column 0 = "Oct 28", column 1 = "Oct 30"
                        trans_date_str = None
                        
                        date_cell_0 = row_list[0] if len(row_list) > 0 else ''
                        date_cell_1 = row_list[1] if len(row_list) > 1 else ''
                        
                        # Check if column 0 has newline (Format 1)
                        if '\n' in date_cell_0:
                            date_parts = [d.strip() for d in date_cell_0.split('\n') if d.strip()]
                            if len(date_parts) >= 1:
                                trans_date_str = date_parts[0]
                        # Check if column 0 and 1 are both dates (Format 2)
                        elif re.match(r'([A-Z][a-z]+)\s+\d{1,2}', date_cell_0, re.IGNORECASE) and re.match(r'([A-Z][a-z]+)\s+\d{1,2}', date_cell_1, re.IGNORECASE):
                            trans_date_str = date_cell_0
                        
                        if not trans_date_str:
                            continue
                        
                        # Description and amount depend on format
                        if '\n' in date_cell_0:
                            # Format 1: dates in col 0, description in col 1, amount in col 2
                            description = row_list[1] if len(row_list) > 1 else ''
                            amount_str = row_list[2] if len(row_list) > 2 else ''
                        else:
                            # Format 2: dates in col 0 and 1, description in col 2, amount in col 4 (or last)
                            description = row_list[2] if len(row_list) > 2 else ''
                            amount_str = row_list[4] if len(row_list) > 4 else (row_list[-1] if len(row_list) > 0 else '')
                        
                        # Parse date (use Transaction date)
                        date_match = re.match(r'([A-Z][a-z]+)\s+(\d{1,2})', trans_date_str, re.IGNORECASE)
                        if not date_match:
                            continue
                        
                        month_name = date_match.group(1).lower()[:3]
                        day = int(date_match.group(2))
                        month = month_map.get(month_name)
                        
                        if not month:
                            continue
                        
                        # Determine year based on statement period
                        # If statement spans two years, use start year for dates in first half of year
                        start_year = int(statement_start_year)
                        end_year = int(statement_end_year)
                        
                        if start_year != end_year:
                            # Statement spans two years (e.g., Dec 2024 to Jan 2025)
                            # Dates in Dec should use start_year, dates in Jan should use end_year
                            if month >= 10:  # Oct, Nov, Dec
                                year_to_use = start_year
                            else:  # Jan, Feb, etc.
                                year_to_use = end_year
                        else:
                            year_to_use = end_year
                        
                        try:
                            full_date = datetime(year_to_use, month, day)
                            date_str = full_date.strftime('%Y-%m-%d')
                        except:
                            continue
                        
                        # Parse amount (payments are positive in PDF, but should be negative for credit card format)
                        amount_clean = amount_str.replace('$', '').replace(',', '').strip()
                        try:
                            amount = float(amount_clean)
                            # Payments should be negative (credit to card = you paid money)
                            amount = -amount
                        except:
                            continue
                        
                        if description:
                            transactions.append({
                                'Date': date_str,
                                'Description': description,
                                'Amount': amount
                            })
        
        # Extract charges section
        if charges_start is not None:
            # Find header row (similar structure)
            header_row = None
            for idx in range(charges_start + 1, min(charges_start + 5, len(df))):
                row_text = ' '.join([str(cell) for cell in df.iloc[idx].tolist()]).upper()
                if 'DATE' in row_text and 'AMOUNT' in row_text:
                    header_row = idx
                    break
            
            if header_row:
                # Parse charge transactions
                for idx in range(header_row + 1, len(df)):
                    row = df.iloc[idx]
                    row_list = [str(cell).strip() for cell in row.tolist()]
                    row_text = ' '.join(row_list).upper()
                    
                    # Stop at total or end
                    if 'TOTAL FOR' in row_text or 'CARD NUMBER' in row_text or not any(row_list):
                        if 'TOTAL FOR' not in row_text:  # Don't break on card number, just skip it
                            continue
                        break
                    
                    # Skip header rows
                    if 'TRANS' in row_text and 'DATE' in row_text:
                        continue
                    
                    # Parse transaction: Trans date, Post date, Description, [Spend Categories], Amount
                    if len(row_list) >= 3:
                        # Dates can be in two formats (same as payments)
                        trans_date_str = None
                        
                        date_cell_0 = row_list[0] if len(row_list) > 0 else ''
                        date_cell_1 = row_list[1] if len(row_list) > 1 else ''
                        
                        # Check if column 0 has newline (Format 1)
                        if '\n' in date_cell_0:
                            date_parts = [d.strip() for d in date_cell_0.split('\n') if d.strip()]
                            if len(date_parts) >= 1:
                                trans_date_str = date_parts[0]
                        # Check if column 0 and 1 are both dates (Format 2)
                        elif re.match(r'([A-Z][a-z]+)\s+\d{1,2}', date_cell_0, re.IGNORECASE) and re.match(r'([A-Z][a-z]+)\s+\d{1,2}', date_cell_1, re.IGNORECASE):
                            trans_date_str = date_cell_0
                        
                        if not trans_date_str:
                            continue
                        
                        # Description and amount depend on format
                        if '\n' in date_cell_0:
                            # Format 1: dates in col 0, description in col 2, amount in last column
                            description = row_list[2] if len(row_list) > 2 else ''
                            amount_str = row_list[-1] if len(row_list) > 0 else ''
                        else:
                            # Format 2: dates in col 0 and 1, description in col 2, amount in last column
                            description = row_list[2] if len(row_list) > 2 else ''
                            amount_str = row_list[-1] if len(row_list) > 0 else ''
                        
                        # Parse date (use Transaction date)
                        date_match = re.match(r'([A-Z][a-z]+)\s+(\d{1,2})', trans_date_str, re.IGNORECASE)
                        if not date_match:
                            continue
                        
                        month_name = date_match.group(1).lower()[:3]
                        day = int(date_match.group(2))
                        month = month_map.get(month_name)
                        
                        if not month:
                            continue
                        
                        # Determine year based on statement period
                        start_year = int(statement_start_year)
                        end_year = int(statement_end_year)
                        
                        if start_year != end_year:
                            # Statement spans two years
                            if month >= 10:  # Oct, Nov, Dec
                                year_to_use = start_year
                            else:  # Jan, Feb, etc.
                                year_to_use = end_year
                        else:
                            year_to_use = end_year
                        
                        try:
                            full_date = datetime(year_to_use, month, day)
                            date_str = full_date.strftime('%Y-%m-%d')
                        except:
                            continue
                        
                        # Parse amount (charges are positive)
                        amount_clean = amount_str.replace('$', '').replace(',', '').strip()
                        try:
                            amount = float(amount_clean)
                            # Charges should be positive (debit to card = you spent money)
                        except:
                            continue
                        
                        if description:
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
    
    return df, opening_balance, closing_balance, statement_year


if __name__ == "__main__":
    # Test on first file
    pdf_dir = Path("data/Account Statements Visa - CIBC 9267")
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {pdf_dir}")
        exit(1)
    
    print(f"Testing CIBC Visa extraction on: {pdf_files[0].name}\n")
    
    df, opening, closing, year = extract_cibc_visa_statement(str(pdf_files[0]))
    
    print(f"Opening Balance: ${opening:,.2f}" if opening else "Opening Balance: None")
    print(f"Closing Balance: ${closing:,.2f}" if closing else "Closing Balance: None")
    print(f"Statement Year: {year}")
    print(f"\nExtracted {len(df)} transactions:\n")
    print(df.to_string())
