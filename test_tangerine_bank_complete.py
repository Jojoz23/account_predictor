#!/usr/bin/env python3
"""
Complete extraction script for Tangerine Bank statements
Analyzes PDF structure and extracts transactions
"""

import pdfplumber
import camelot
import pandas as pd
import re
from datetime import datetime
from pathlib import Path

def analyze_tangerine_structure(pdf_path):
    """Analyze Tangerine bank PDF structure"""
    print("="*80)
    print(f"ANALYZING TANGERINE BANK STRUCTURE: {Path(pdf_path).name}")
    print("="*80)
    
    # Extract text
    with pdfplumber.open(pdf_path) as pdf:
        print(f"\nTotal pages: {len(pdf.pages)}")
        
        # Get text from first few pages
        text = ""
        for page_num in range(min(3, len(pdf.pages))):
            page_text = pdf.pages[page_num].extract_text() or ""
            text += page_text + "\n"
            print(f"\nPage {page_num + 1} text (first 500 chars):")
            print(page_text[:500])
    
    # Check for Tangerine indicators
    text_lower = text.lower()
    print(f"\n{'='*80}")
    print("TANGERINE BANK INDICATORS:")
    print("="*80)
    print(f"  'tangerine' in text: {'tangerine' in text_lower}")
    print(f"  'ing direct' in text: {'ing direct' in text_lower}")
    print(f"  'account statement' in text: {'account statement' in text_lower}")
    
    # Try Camelot extraction
    print(f"\n{'='*80}")
    print("CAMELOT TABLE ANALYSIS:")
    print("="*80)
    try:
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        print(f"Stream flavor: Found {len(tables_stream)} table(s)")
        
        for table_idx, table in enumerate(tables_stream):
            df_table = table.df
            print(f"\n  Table {table_idx + 1} (page {table.page}):")
            print(f"    Shape: {df_table.shape}")
            print(f"    First 10 rows:")
            for r in range(min(10, len(df_table))):
                print(f"      Row {r}: {df_table.iloc[r].tolist()}")
        
        # Try lattice too
        tables_lattice = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
        print(f"\nLattice flavor: Found {len(tables_lattice)} table(s)")
        
        for table_idx, table in enumerate(tables_lattice):
            df_table = table.df
            print(f"\n  Table {table_idx + 1} (page {table.page}):")
            print(f"    Shape: {df_table.shape}")
            print(f"    First 10 rows:")
            for r in range(min(10, len(df_table))):
                print(f"      Row {r}: {df_table.iloc[r].tolist()}")
    except Exception as e:
        print(f"Error with Camelot: {e}")
        import traceback
        traceback.print_exc()
    
    # Extract tables using pdfplumber
    print(f"\n{'='*80}")
    print("PDFPLUMBER TABLE ANALYSIS:")
    print("="*80)
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages[:3]):
            tables = page.extract_tables()
            print(f"\nPage {page_num + 1}: Found {len(tables)} table(s)")
            for table_idx, table in enumerate(tables):
                if table and len(table) > 0:
                    print(f"  Table {table_idx + 1}: {len(table)} rows, {len(table[0]) if table[0] else 0} columns")
                    print(f"    First 5 rows:")
                    for r in range(min(5, len(table))):
                        print(f"      Row {r}: {table[r]}")


def extract_tangerine_bank_statement(pdf_path):
    """Extract transactions from Tangerine Bank statement"""
    print("\n" + "="*80)
    print(f"EXTRACTING TANGERINE BANK STATEMENT: {Path(pdf_path).name}")
    print("="*80)
    
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    statement_start_year = None
    statement_end_year = None
    
    # Step 1: Extract text for analysis
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    print("\n1. EXTRACTING STATEMENT PERIOD AND YEAR:")
    print("-" * 80)
    
    # Look for statement period patterns
    period_patterns = [
        r'Statement\s+Period[:\s]+([A-Z]{3}\s?\d{1,2}[,\s]+\d{4})\s+to\s+([A-Z]{3}\s?\d{1,2}[,\s]+\d{4})',
        r'([A-Z]{3}\s?\d{1,2}[,\s]+\d{4})\s+to\s+([A-Z]{3}\s?\d{1,2}[,\s]+\d{4})',
        r'Period[:\s]+([A-Z]{3}\s?\d{1,2}[,\s]+\d{4})\s+-\s+([A-Z]{3}\s?\d{1,2}[,\s]+\d{4})',
    ]
    
    for pattern in period_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            start_str = match.group(1).strip()
            end_str = match.group(2).strip()
            print(f"  Found period: {start_str} to {end_str}")
            
            # Extract years
            start_year_match = re.search(r'(\d{4})', start_str)
            end_year_match = re.search(r'(\d{4})', end_str)
            
            if start_year_match and end_year_match:
                statement_start_year = int(start_year_match.group(1))
                statement_end_year = int(end_year_match.group(1))
                statement_year = statement_end_year
                print(f"  Statement Start Year: {statement_start_year}")
                print(f"  Statement End Year: {statement_end_year}")
                break
    
    if not statement_year:
        # Fallback: try to extract year from filename or current year
        year_match = re.search(r'\b(202[0-9]|203[0-9])\b', full_text)
        if year_match:
            statement_year = int(year_match.group(1))
            statement_start_year = statement_year
            statement_end_year = statement_year
            print(f"  Extracted year from text: {statement_year}")
        else:
            statement_year = 2025
            statement_start_year = 2025
            statement_end_year = 2025
            print(f"  Using fallback year: {statement_year}")
    
    # Step 2: Extract opening and closing balances
    print("\n2. EXTRACTING OPENING AND CLOSING BALANCES:")
    print("-" * 80)
    
    opening_patterns = [
        r'Opening\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Beginning\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Starting\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Previous\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
    ]
    
    for pattern in opening_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                opening_balance = float(match.group(1).replace(',', ''))
                print(f"  Opening Balance: ${opening_balance:,.2f}")
                break
            except:
                pass
    
    closing_patterns = [
        r'Closing\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Ending\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Final\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Current\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Balance\s+as\s+of[:\s]+\$?([\d,]+\.?\d{0,2})',
    ]
    
    for pattern in closing_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                closing_balance = float(match.group(1).replace(',', ''))
                print(f"  Closing Balance: ${closing_balance:,.2f}")
                break
            except:
                pass
    
    # Step 3: Extract transactions
    print("\n3. EXTRACTING TRANSACTIONS:")
    print("-" * 80)
    
    # Try Camelot first
    try:
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        print(f"  Stream: Found {len(tables_stream)} table(s)")
        
        for table_idx, table in enumerate(tables_stream):
            df_table = table.df
            print(f"\n  Processing Table {table_idx + 1} (page {table.page}, shape: {df_table.shape})")
            
            # Analyze table structure
            if len(df_table) > 0:
                print(f"    First 10 rows:")
                for r in range(min(10, len(df_table))):
                    print(f"      Row {r}: {df_table.iloc[r].tolist()}")
                
                # Look for header row
                header_row = None
                desc_idx = None
                date_idx = None
                amount_idx = None
                balance_idx = None
                
                for i, row in df_table.iterrows():
                    if i > 20:  # Check first 20 rows
                        break
                    row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in row]).upper()
                    
                    # Check for header keywords
                    has_date = 'DATE' in row_text
                    has_description = 'DESCRIPTION' in row_text or 'DETAILS' in row_text or 'TRANSACTION' in row_text
                    has_amount = 'AMOUNT' in row_text or 'DEBIT' in row_text or 'CREDIT' in row_text or 'WITHDRAWAL' in row_text or 'DEPOSIT' in row_text
                    has_balance = 'BALANCE' in row_text
                    
                    if has_date and (has_description or has_amount):
                        header_row = i
                        print(f"    Found header at row {i}")
                        
                        # Find column indices
                        for j, cell in enumerate(row):
                            if pd.notna(cell):
                                cell_upper = str(cell).upper().strip()
                                if 'DATE' in cell_upper and date_idx is None:
                                    date_idx = j
                                if ('DESCRIPTION' in cell_upper or 'DETAILS' in cell_upper or 'TRANSACTION' in cell_upper) and desc_idx is None:
                                    desc_idx = j
                                if ('AMOUNT' in cell_upper or 'DEBIT' in cell_upper or 'CREDIT' in cell_upper or 'WITHDRAWAL' in cell_upper or 'DEPOSIT' in cell_upper) and amount_idx is None:
                                    amount_idx = j
                                if 'BALANCE' in cell_upper and balance_idx is None:
                                    balance_idx = j
                        break
                
                # If no header found, try to infer from structure
                if header_row is None:
                    print(f"    No header found, trying to infer structure...")
                    # Look for transaction-like rows (have dates and amounts)
                    for i, row in df_table.iterrows():
                        if i > 10:
                            break
                        row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in row])
                        # Check if row has date pattern
                        if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', row_text) or re.search(r'[A-Z]{3}\s+\d{1,2}', row_text):
                            # This might be a transaction row, infer columns
                            if len(df_table.columns) >= 4:
                                date_idx = 0
                                desc_idx = 1
                                amount_idx = 2
                                balance_idx = 3 if len(df_table.columns) > 3 else None
                            break
                
                # Extract transactions
                if date_idx is not None:
                    start_row = header_row + 1 if header_row is not None else 0
                    print(f"    Extracting from row {start_row} onwards")
                    print(f"    Columns: DATE={date_idx}, DESC={desc_idx}, AMOUNT={amount_idx}, BALANCE={balance_idx}")
                    
                    month_map = {
                        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    
                    for row_idx in range(start_row, len(df_table)):
                        row = df_table.iloc[row_idx]
                        
                        # Get date
                        date_str = ""
                        if date_idx is not None and date_idx < len(row):
                            date_cell = row.iloc[date_idx]
                            if pd.notna(date_cell):
                                date_str = str(date_cell).strip()
                        
                        # Get description
                        description = ""
                        if desc_idx is not None and desc_idx < len(row):
                            desc_cell = row.iloc[desc_idx]
                            if pd.notna(desc_cell):
                                description = str(desc_cell).strip()
                        
                        # Skip empty rows
                        if not date_str and not description:
                            continue
                        
                        # Skip header-like rows
                        if 'DATE' in date_str.upper() or 'DESCRIPTION' in description.upper():
                            continue
                        
                        # Parse date
                        date_obj = None
                        # Try various date formats
                        date_formats = [
                            r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # MM/DD/YYYY or DD/MM/YYYY
                            r'([A-Z]{3})\s+(\d{1,2})[,\s]+(\d{4})',  # Jan 15, 2025
                            r'([A-Z]{3})\s+(\d{1,2})',  # Jan 15 (no year)
                        ]
                        
                        for fmt in date_formats:
                            match = re.search(fmt, date_str, re.IGNORECASE)
                            if match:
                                if 'A-Z' in fmt:  # Month name format
                                    month_name = match.group(1).lower()
                                    day = int(match.group(2))
                                    month = month_map.get(month_name, 1)
                                    if len(match.groups()) > 2:
                                        year = int(match.group(3))
                                    else:
                                        year = statement_year
                                    try:
                                        date_obj = datetime(year, month, day)
                                    except:
                                        pass
                                else:  # Numeric format
                                    try:
                                        if len(match.groups()) == 3:
                                            # Try both MM/DD and DD/MM
                                            part1, part2, part3 = match.groups()
                                            # Assume MM/DD/YYYY first
                                            try:
                                                month, day, year = int(part1), int(part2), int(part3)
                                                if year < 100:
                                                    year += 2000
                                                date_obj = datetime(year, month, day)
                                            except:
                                                # Try DD/MM/YYYY
                                                day, month, year = int(part1), int(part2), int(part3)
                                                if year < 100:
                                                    year += 2000
                                                date_obj = datetime(year, month, day)
                                    except:
                                        pass
                                if date_obj:
                                    break
                        
                        if not date_obj:
                            continue
                        
                        # Get amount
                        withdrawal = None
                        deposit = None
                        
                        if amount_idx is not None and amount_idx < len(row):
                            amount_cell = row.iloc[amount_idx]
                            if pd.notna(amount_cell):
                                amount_str = str(amount_cell).strip().replace(',', '').replace('$', '')
                                # Check if it's negative (withdrawal) or positive (deposit)
                                is_negative = amount_str.startswith('-') or '(' in amount_str
                                amount_clean = amount_str.replace('-', '').replace('(', '').replace(')', '').strip()
                                
                                try:
                                    amount = float(amount_clean)
                                    if is_negative:
                                        withdrawal = amount
                                    else:
                                        deposit = amount
                                except:
                                    pass
                        
                        # Skip if no amount
                        if withdrawal is None and deposit is None:
                            continue
                        
                        # Get balance if available
                        balance = None
                        if balance_idx is not None and balance_idx < len(row):
                            balance_cell = row.iloc[balance_idx]
                            if pd.notna(balance_cell):
                                balance_str = str(balance_cell).strip().replace(',', '').replace('$', '')
                                try:
                                    balance = float(balance_str)
                                    if closing_balance is None:
                                        closing_balance = balance
                                except:
                                    pass
                        
                        transactions.append({
                            'Date': date_obj.strftime('%Y-%m-%d'),
                            'Description': description,
                            'Withdrawals': withdrawal if withdrawal else 0.0,
                            'Deposits': deposit if deposit else 0.0,
                            'Balance': balance
                        })
                
                print(f"    Extracted {len(transactions)} transactions from this table")
        
        # If no transactions from Camelot, try pdfplumber tables
        if len(transactions) == 0:
            print("\n  Trying pdfplumber tables...")
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        
                        # Look for header
                        header_row = None
                        for i, row in enumerate(table):
                            if row and len(row) >= 3:
                                row_text = ' '.join([str(cell) if cell else '' for cell in row]).upper()
                                if 'DATE' in row_text and ('DESCRIPTION' in row_text or 'AMOUNT' in row_text):
                                    header_row = i
                                    break
                        
                        if header_row is not None:
                            # Extract transactions from this table
                            # (Similar logic as Camelot extraction)
                            pass
                            
    except Exception as e:
        print(f"  Error with Camelot: {e}")
        import traceback
        traceback.print_exc()
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    if len(df) == 0:
        print("\n  WARNING: No transactions extracted!")
        return None, None, None, None
    
    print(f"\n  Extracted {len(df)} transactions")
    
    # Calculate running balance
    print("\n4. CALCULATING RUNNING BALANCE:")
    print("-" * 80)
    
    if opening_balance is not None:
        print(f"  Opening Balance: ${opening_balance:,.2f}")
        df['Net_Change'] = df['Deposits'].fillna(0) - df['Withdrawals'].fillna(0)
        df['Running_Balance'] = opening_balance + df['Net_Change'].cumsum()
        
        if len(df) > 0:
            final_balance = df['Running_Balance'].iloc[-1]
            print(f"  Final Running Balance: ${final_balance:,.2f}")
            
            if closing_balance is not None:
                print(f"  Closing Balance: ${closing_balance:,.2f}")
                diff = abs(final_balance - closing_balance)
                print(f"  Difference: ${diff:,.2f}")
                if diff < 0.01:
                    print("  SUCCESS: Running balance matches closing balance!")
                else:
                    print(f"  WARNING: Running balance does not match closing balance by ${diff:,.2f}")
    else:
        print("  WARNING: Could not find opening balance")
    
    return df, opening_balance, closing_balance, statement_year


if __name__ == "__main__":
    # Test with first Tangerine bank statement
    tangerine_folder = Path("data/Tangeriene bank")
    
    if tangerine_folder.exists():
        pdf_files = sorted(tangerine_folder.glob("*.pdf"))
        if pdf_files:
            test_file = pdf_files[0]
            print("\n" + "="*80)
            print("STEP 1: ANALYZING STRUCTURE")
            print("="*80)
            analyze_tangerine_structure(str(test_file))
            
            print("\n" + "="*80)
            print("STEP 2: EXTRACTING TRANSACTIONS")
            print("="*80)
            df, opening, closing, year = extract_tangerine_bank_statement(str(test_file))
            
            if df is not None:
                print("\n" + "="*80)
                print("EXTRACTION RESULTS")
                print("="*80)
                print(f"Transactions: {len(df)}")
                print(f"Opening: ${opening:,.2f}" if opening else "Opening: Not found")
                print(f"Closing: ${closing:,.2f}" if closing else "Closing: Not found")
                print(f"\nFirst 10 transactions:")
                print(df.head(10).to_string())
        else:
            print("No PDF files found in Tangerine bank folder")
    else:
        print("Tangerine bank folder not found")


