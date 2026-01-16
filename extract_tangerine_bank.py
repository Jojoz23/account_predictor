#!/usr/bin/env python3
"""
Tangerine Bank Statement Extractor
Extracts transactions from Tangerine Bank PDF statements
"""

import pdfplumber
import camelot
import pandas as pd
import re
from datetime import datetime
from pathlib import Path
import sys
import io


def extract_tangerine_bank_statement(pdf_path):
    """
    Extract transactions from Tangerine Bank statement
    
    Returns:
        tuple: (DataFrame, opening_balance, closing_balance, statement_year)
    """
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    
    # Step 1: Extract text for year detection
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    # Extract statement year
    year_match = re.search(r'\b(202[0-9]|203[0-9])\b', full_text)
    if year_match:
        statement_year = int(year_match.group(1))
    else:
        statement_year = 2024  # Fallback
    
    # Step 2: Extract transactions using Camelot
    try:
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        # Find the main account transaction table (usually first transaction table on page 1)
        # Skip account summary tables and GIC tables
        main_table_found = False
        
        # Process each table
        for table_idx, table in enumerate(tables_stream):
            df_table = table.df
            
            # Check if this table looks like a GIC table before processing
            # Look at first few rows for GIC keywords
            table_text = ""
            for i in range(min(5, len(df_table))):
                row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in df_table.iloc[i]]).upper()
                table_text += row_text + " "
            
            # Skip GIC tables (they have GIC-specific headers)
            if 'GIC #' in table_text or ('MATURITY' in table_text and 'INSTRUCTIONS' in table_text):
                continue  # Skip GIC account tables
            
            # Look for transaction table header
            header_row = None
            date_idx = None
            desc_idx = None
            amount_idx = None
            balance_idx = None
            
            for i, row in df_table.iterrows():
                if i > 20:  # Check first 20 rows to find header
                    break
                    
                row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in row]).upper()
                
                # Check if this is a transaction header row
                has_date = 'TRANSACTION DATE' in row_text or ('DATE' in row_text and 'TRANSACTION' in row_text)
                has_desc = 'TRANSACTION DESCRIPTION' in row_text or ('DESCRIPTION' in row_text and 'TRANSACTION' in row_text)
                has_amount = 'AMOUNT' in row_text or '$' in row_text
                has_balance = 'BALANCE' in row_text
                
                if has_date and (has_desc or has_amount):
                    header_row = i
                    
                    # Find column indices
                    for j, cell in enumerate(row):
                        if pd.notna(cell):
                            cell_upper = str(cell).upper().strip()
                            if ('DATE' in cell_upper or 'TRANSACTION DATE' in cell_upper) and date_idx is None:
                                date_idx = j
                            if ('DESCRIPTION' in cell_upper or 'TRANSACTION DESCRIPTION' in cell_upper) and desc_idx is None:
                                desc_idx = j
                            # Check for combined Amount/Balance column (e.g., "Amount($)\nBalance($)")
                            if 'AMOUNT' in cell_upper and 'BALANCE' in cell_upper:
                                if amount_idx is None:
                                    amount_idx = j
                                if balance_idx is None:
                                    balance_idx = j
                            elif 'AMOUNT' in cell_upper and amount_idx is None:
                                amount_idx = j
                            elif 'BALANCE' in cell_upper and balance_idx is None:
                                balance_idx = j
                    
                    # For Tangerine, columns are typically:
                    # Transaction Date | Transaction Description | Amount($) | Balance($)
                    # If we found DATE but not DESC, check if next column has description
                    if date_idx is not None and desc_idx is None:
                        # Check if there's a description column after date
                        if date_idx + 1 < len(row):
                            next_cell = str(row.iloc[date_idx + 1]).upper() if pd.notna(row.iloc[date_idx + 1]) else ""
                            if 'DESCRIPTION' in next_cell or 'TRANSACTION' in next_cell:
                                desc_idx = date_idx + 1
                    
                    # If we still don't have desc_idx, try to infer from structure
                    if date_idx is not None and desc_idx is None and date_idx + 1 < len(df_table.columns):
                        desc_idx = date_idx + 1
                    
                    # Infer amount and balance indices if not found
                    if desc_idx is not None:
                        if amount_idx is None and desc_idx + 1 < len(df_table.columns):
                            amount_idx = desc_idx + 1
                        if balance_idx is None and desc_idx + 2 < len(df_table.columns):
                            balance_idx = desc_idx + 2
                    
                    break
            
            # If we found a valid transaction table, extract transactions
            # Only process the main account table (first one we find, skip subsequent ones)
            if header_row is not None and date_idx is not None and not main_table_found:
                main_table_found = True
                start_row = header_row + 1
                
                for row_idx in range(start_row, len(df_table)):
                    row = df_table.iloc[row_idx]
                    
                    # Get date
                    date_str = ""
                    if date_idx is not None and date_idx < len(row):
                        date_cell = row.iloc[date_idx]
                        if pd.notna(date_cell):
                            date_str = str(date_cell).strip()
                            # Handle case where date and description are combined (e.g., "31 Jan 2025\nInterest Paid")
                            if '\n' in date_str:
                                lines = [line.strip() for line in date_str.split('\n') if line.strip()]
                                if lines:
                                    date_str = lines[0]  # First line is the date
                    
                    # Get description
                    description = ""
                    if desc_idx is not None and desc_idx < len(row):
                        desc_cell = row.iloc[desc_idx]
                        if pd.notna(desc_cell):
                            description = str(desc_cell).strip()
                    # If description is empty but date cell has multiple lines, use second line as description
                    if not description and date_idx is not None and date_idx < len(row):
                        date_cell = row.iloc[date_idx]
                        if pd.notna(date_cell):
                            date_cell_str = str(date_cell).strip()
                            if '\n' in date_cell_str:
                                lines = [line.strip() for line in date_cell_str.split('\n') if line.strip()]
                                if len(lines) >= 2:
                                    description = lines[1]  # Second line is the description
                    
                    # Skip empty rows
                    if not date_str:
                        continue
                    
                    # Skip header-like rows
                    if 'DATE' in date_str.upper() or 'TRANSACTION' in date_str.upper():
                        continue
                    
                    # Handle Opening/Closing Balance rows
                    desc_upper = description.upper()
                    is_opening_balance = 'OPENING BALANCE' in desc_upper
                    is_closing_balance = 'CLOSING BALANCE' in desc_upper
                    
                    if is_opening_balance or is_closing_balance:
                        # Extract balance from this row
                        # Check if amount and balance are in the same column (combined format)
                        is_combined = (amount_idx is not None and balance_idx is not None and amount_idx == balance_idx)
                        
                        if balance_idx is not None and balance_idx < len(row):
                            balance_cell = row.iloc[balance_idx]
                            if pd.notna(balance_cell):
                                balance_str = None
                                if is_combined:
                                    # Combined format: extract balance from second line
                                    combined_str = str(balance_cell).strip()
                                    lines = [line.strip() for line in combined_str.split('\n') if line.strip()]
                                    if len(lines) >= 2:
                                        balance_str = lines[1].replace(',', '').replace('$', '').strip()
                                    elif len(lines) == 1:
                                        # Try the single line as balance
                                        balance_str = lines[0].replace(',', '').replace('$', '').strip()
                                else:
                                    # Separate column format
                                    balance_str = str(balance_cell).strip().replace(',', '').replace('$', '')
                                
                                if balance_str:
                                    try:
                                        balance_val = float(balance_str)
                                        if is_opening_balance and opening_balance is None:
                                            opening_balance = balance_val
                                        elif is_closing_balance and closing_balance is None:
                                            closing_balance = balance_val
                                    except:
                                        pass
                        continue  # Skip these rows as transactions (they're just markers)
                    
                    # Parse date - Tangerine format: "01 Dec 2024" or "Dec 01, 2024"
                    date_obj = None
                    date_patterns = [
                        r'(\d{1,2})\s+([A-Z]{3})\s+(\d{4})',  # 01 Dec 2024
                        r'([A-Z]{3})\s+(\d{1,2})[,\s]+(\d{4})',  # Dec 01, 2024
                        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # MM/DD/YYYY
                    ]
                    
                    for pattern_idx, pattern in enumerate(date_patterns):
                        match = re.search(pattern, date_str, re.IGNORECASE)
                        if match:
                            # First two patterns are month name formats, third is numeric
                            if pattern_idx < 2:  # Month name format
                                if len(match.groups()) == 3:
                                    if pattern_idx == 0:  # 01 Dec 2024 format
                                        day = int(match.group(1))
                                        month_name = match.group(2).lower()
                                        year = int(match.group(3))
                                    else:  # Dec 01, 2024 format
                                        month_name = match.group(1).lower()
                                        day = int(match.group(2))
                                        year = int(match.group(3))
                                    
                                    month = month_map.get(month_name, 1)
                                    try:
                                        date_obj = datetime(year, month, day)
                                        break
                                    except:
                                        pass
                            else:  # Numeric format (MM/DD/YYYY)
                                try:
                                    part1, part2, part3 = match.groups()
                                    month, day = int(part1), int(part2)
                                    year = int(part3)
                                    if year < 100:
                                        year += 2000
                                    date_obj = datetime(year, month, day)
                                    break
                                except:
                                    pass
                    
                    if not date_obj:
                        continue
                    
                    # Get amount and balance
                    # Check if amount and balance are in the same column (combined format)
                    is_combined_amount_balance = (amount_idx is not None and balance_idx is not None and amount_idx == balance_idx)
                    
                    balance = None
                    amount = None
                    withdrawal = None
                    deposit = None
                    
                    if is_combined_amount_balance:
                        # Combined format: "Amount\nBalance" in one cell (e.g., "0.00\n268,601.34")
                        if amount_idx < len(row):
                            combined_cell = row.iloc[amount_idx]
                            if pd.notna(combined_cell):
                                combined_str = str(combined_cell).strip()
                                # Split by newline
                                lines = [line.strip() for line in combined_str.split('\n') if line.strip()]
                                if len(lines) >= 2:
                                    # First line is amount, second line is balance
                                    amount_str = lines[0].replace(',', '').replace('$', '').strip()
                                    balance_str = lines[1].replace(',', '').replace('$', '').strip()
                                elif len(lines) == 1:
                                    # Only one line - try to parse as amount
                                    amount_str = lines[0].replace(',', '').replace('$', '').strip()
                                    balance_str = None
                                else:
                                    amount_str = None
                                    balance_str = None
                                
                                # Parse amount
                                if amount_str:
                                    is_negative_in_str = amount_str.startswith('-') or '(' in amount_str
                                    amount_clean = amount_str.replace('-', '').replace('(', '').replace(')', '').strip()
                                    try:
                                        amount = float(amount_clean)
                                    except:
                                        pass
                                
                                # Parse balance
                                if balance_str:
                                    try:
                                        balance = float(balance_str)
                                    except:
                                        pass
                    else:
                        # Separate columns format
                        # Get balance first (we'll use it to determine if amount is deposit or withdrawal)
                        if balance_idx is not None and balance_idx < len(row):
                            balance_cell = row.iloc[balance_idx]
                            if pd.notna(balance_cell):
                                balance_str = str(balance_cell).strip().replace(',', '').replace('$', '')
                                try:
                                    balance = float(balance_str)
                                except:
                                    pass
                        
                        # Get amount
                        if amount_idx is not None and amount_idx < len(row):
                            amount_cell = row.iloc[amount_idx]
                            if pd.notna(amount_cell):
                                amount_str = str(amount_cell).strip().replace(',', '').replace('$', '')
                                
                                # Clean amount string
                                is_negative_in_str = amount_str.startswith('-') or '(' in amount_str
                                amount_clean = amount_str.replace('-', '').replace('(', '').replace(')', '').strip()
                                
                                try:
                                    amount = float(amount_clean)
                                except:
                                    pass
                    
                    # Don't skip $0 transactions - user wants to keep them
                    if amount is None:
                        continue
                    
                    # Determine if it's a deposit or withdrawal based on balance change
                    # Compare with previous balance (or opening balance for first transaction)
                    if balance is not None:
                        # Determine previous balance
                        if len(transactions) > 0:
                            # Use last transaction's balance
                            prev_balance = transactions[-1].get('Balance')
                        elif opening_balance is not None:
                            # Use opening balance for first transaction
                            prev_balance = opening_balance
                        else:
                            prev_balance = None
                        
                        if prev_balance is not None:
                            balance_change = balance - prev_balance
                            
                            # If balance increased, it's a deposit
                            # If balance decreased, it's a withdrawal
                            if abs(balance_change - amount) < 0.01:  # Balance increased by amount = deposit
                                deposit = amount
                            elif abs(balance_change + amount) < 0.01:  # Balance decreased by amount = withdrawal
                                withdrawal = amount
                            else:
                                # Balance change doesn't match amount exactly - use direction
                                if balance_change > 0:
                                    deposit = amount
                                else:
                                    withdrawal = amount
                        else:
                            # No previous balance available - use heuristics
                            # ALL CAPS descriptions often indicate withdrawals
                            desc_upper = description.upper()
                            if description == desc_upper and len(description) > 3:  # All caps
                                withdrawal = amount
                            else:
                                deposit = amount
                    else:
                        # No balance available - use heuristics
                        desc_upper = description.upper()
                        if description == desc_upper and len(description) > 3:  # All caps
                            withdrawal = amount
                        else:
                            deposit = amount
                    
                    transactions.append({
                        'Date': date_obj.strftime('%Y-%m-%d'),
                        'Description': description,
                        'Withdrawals': withdrawal if withdrawal else 0.0,
                        'Deposits': deposit if deposit else 0.0,
                        'Balance': balance
                    })
        
        # If we still don't have closing balance, use last transaction's balance
        if closing_balance is None and transactions:
            last_txn = transactions[-1]
            if last_txn.get('Balance') is not None:
                closing_balance = last_txn['Balance']
                
    except Exception as e:
        print(f"Error extracting with Camelot: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None
    
    # Create DataFrame
    if not transactions:
        return None, None, None, None
    
    df = pd.DataFrame(transactions)
    
    # Sort by date
    df = df.sort_values('Date').reset_index(drop=True)
    
    # Calculate running balance
    if opening_balance is not None:
        df['Net_Change'] = df['Deposits'].fillna(0) - df['Withdrawals'].fillna(0)
        df['Running_Balance'] = opening_balance + df['Net_Change'].cumsum()
    
    return df, opening_balance, closing_balance, statement_year


if __name__ == "__main__":
    # Fix encoding for Windows
    if sys.platform == 'win32':
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except:
            pass
    
    # Test with a Tangerine bank statement
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        tangerine_folder = Path("data/Tangeriene bank")
        if tangerine_folder.exists():
            pdf_files = sorted(tangerine_folder.glob("*.pdf"))
            if pdf_files:
                pdf_path = str(pdf_files[0])
            else:
                print("No PDF files found in Tangerine bank folder")
                sys.exit(1)
        else:
            print("Tangerine bank folder not found")
            sys.exit(1)
    
    print("="*80)
    print(f"EXTRACTING TANGERINE BANK STATEMENT: {Path(pdf_path).name}")
    print("="*80)
    
    df, opening, closing, year = extract_tangerine_bank_statement(pdf_path)
    
    if df is not None:
        print(f"\n✅ Extraction successful!")
        print(f"   Transactions: {len(df)}")
        print(f"   Opening Balance: ${opening:,.2f}" if opening else "   Opening Balance: Not found")
        print(f"   Closing Balance: ${closing:,.2f}" if closing else "   Closing Balance: Not found")
        print(f"   Statement Year: {year}")
        
        if 'Running_Balance' in df.columns and closing:
            final_rb = df['Running_Balance'].iloc[-1]
            diff = abs(final_rb - closing)
            print(f"   Final Running Balance: ${final_rb:,.2f}")
            print(f"   Difference: ${diff:,.2f}")
            if diff < 0.01:
                print("   ✅ Running balance matches closing balance!")
            else:
                print(f"   ⚠️  Running balance differs by ${diff:,.2f}")
        
        print(f"\nFirst 10 transactions:")
        cols = ['Date', 'Description', 'Withdrawals', 'Deposits']
        if 'Balance' in df.columns:
            cols.append('Balance')
        if 'Running_Balance' in df.columns:
            cols.append('Running_Balance')
        print(df[cols].head(10).to_string())
    else:
        print("\n❌ Extraction failed")

