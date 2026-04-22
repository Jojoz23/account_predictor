#!/usr/bin/env python3
"""
Complete test script for TD Bank statement extraction
"""

import pdfplumber
import camelot
import pandas as pd
import re
from datetime import datetime
from pathlib import Path

def _parse_td_balance(value):
    """Parse TD balance strings, including overdraft suffix like '23,122.61OD'."""
    if value is None:
        return None
    s = str(value).strip().upper().replace("$", "").replace(",", "").replace(" ", "")
    if not s:
        return None
    is_od = "OD" in s
    s = s.replace("OD", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    amt = float(m.group(0))
    return -abs(amt) if is_od else amt

def extract_td_bank_statement(pdf_path):
    """Extract transactions from TD Bank statement"""
    print(f"\n{'='*70}")
    print(f"Extracting: {Path(pdf_path).name}")
    print(f"{'='*70}\n")
    
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    statement_start_year = None
    statement_end_year = None
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    # Extract statement period and year
    print("1. EXTRACTING STATEMENT PERIOD:")
    print("-" * 70)
    
    # Pattern: "DEC31/24 - JAN 31/25" or "DEC 31/24 - JAN 31/25"
    period_match = re.search(r'Statement From - To\s+([A-Z]{3}\s?\d{1,2}/\d{2})\s*-\s*([A-Z]{3}\s?\d{1,2}/\d{2})', full_text, re.IGNORECASE)
    if not period_match:
        # Try alternative pattern
        period_match = re.search(r'([A-Z]{3}\s?\d{1,2}/\d{2})\s*-\s*([A-Z]{3}\s?\d{1,2}/\d{2})', full_text, re.IGNORECASE)
    
    if period_match:
        start_str = period_match.group(1).strip()
        end_str = period_match.group(2).strip()
        print(f"  Statement Period: {start_str} to {end_str}")
        
        # Extract years (format: DEC31/24 means year 2024)
        start_year_match = re.search(r'/(\d{2})$', start_str)
        end_year_match = re.search(r'/(\d{2})$', end_str)
        
        if start_year_match and end_year_match:
            start_year_short = int(start_year_match.group(1))
            end_year_short = int(end_year_match.group(1))
            
            # Convert to full year (assuming 2000s)
            statement_start_year = 2000 + start_year_short
            statement_end_year = 2000 + end_year_short
            
            # Use end year as primary statement year
            statement_year = statement_end_year
            
            print(f"  Statement Start Year: {statement_start_year}")
            print(f"  Statement End Year: {statement_end_year}")
            print(f"  Primary Statement Year: {statement_year}")
    else:
        print("  WARNING: Could not extract statement period")
        # Fallback: try to extract year from filename or current year
        statement_year = 2025
        statement_start_year = 2024
        statement_end_year = 2025
        print(f"  Using fallback year: {statement_year}")
    
    # Extract account number
    account_match = re.search(r'Account No\.\s+(\d+-\d+)', full_text, re.IGNORECASE)
    if account_match:
        account_number = account_match.group(1)
        print(f"\n  Account Number: {account_number}")
    
    # Extract transactions from tables
    print("\n2. EXTRACTING TRANSACTIONS:")
    print("-" * 70)
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            
            for table in tables:
                if not table or len(table) < 2:
                    continue
                
                # Look for transaction table header
                header_row = None
                for i, row in enumerate(table):
                    if row and len(row) >= 5:
                        row_text = ' '.join([str(cell) if cell else '' for cell in row]).upper()
                        if 'DESCRIPTION' in row_text and ('DEBIT' in row_text or 'DEPOSIT' in row_text) and 'DATE' in row_text:
                            header_row = i
                            break
                
                if header_row is None:
                    continue
                
                # Parse header to find column indices
                header = table[header_row]
                desc_idx = None
                debit_idx = None
                credit_idx = None
                date_idx = None
                balance_idx = None
                
                for i, cell in enumerate(header):
                    if cell:
                        cell_upper = str(cell).upper()
                        if 'DESCRIPTION' in cell_upper:
                            desc_idx = i
                        elif 'DEBIT' in cell_upper or 'CHEQUE' in cell_upper:
                            debit_idx = i
                        elif 'DEPOSIT' in cell_upper or 'CREDIT' in cell_upper:
                            credit_idx = i
                        elif 'DATE' in cell_upper:
                            date_idx = i
                        elif 'BALANCE' in cell_upper:
                            balance_idx = i
                
                if desc_idx is None or date_idx is None:
                    continue
                
                print(f"  Found transaction table on page {page_num + 1}")
                print(f"    Columns: DESC={desc_idx}, DEBIT={debit_idx}, CREDIT={credit_idx}, DATE={date_idx}, BALANCE={balance_idx}")
                
                # Parse transactions
                for row_idx in range(header_row + 1, len(table)):
                    row = table[row_idx]
                    if not row or len(row) <= max(desc_idx, date_idx):
                        continue
                    
                    description = str(row[desc_idx]).strip() if desc_idx < len(row) and row[desc_idx] else ""
                    date_str = str(row[date_idx]).strip() if date_idx < len(row) and row[date_idx] else ""
                    
                    # Skip empty rows
                    if not description and not date_str:
                        continue
                    
                    # Check for opening balance (BALANCE FORWARD)
                    if 'BALANCE FORWARD' in description.upper():
                        balance_str = str(row[balance_idx]).strip() if balance_idx and balance_idx < len(row) and row[balance_idx] else ""
                        if balance_str:
                            balance_str = balance_str.replace(',', '').replace('$', '').strip()
                            try:
                                # Keep the first statement-level opening balance only.
                                # Later BALANCE FORWARD rows (continuation pages/tables) should not overwrite it.
                                if opening_balance is None:
                                    parsed = _parse_td_balance(balance_str)
                                    if parsed is not None:
                                        opening_balance = parsed
                                    print(f"    Opening Balance: ${opening_balance:,.2f}")
                            except:
                                pass
                        continue
                    
                    # Skip summary rows
                    if any(keyword in description.upper() for keyword in ['MONTHLY', 'NEXT STATEMENT', 'DEP CONTENT', 'ITEMS', 'UNC BATCH', 'LIMIT:', 'CREDITS', 'DEBITS']):
                        continue
                    
                    # Extract amounts
                    withdrawal = None
                    deposit = None
                    
                    if debit_idx is not None and debit_idx < len(row) and row[debit_idx]:
                        debit_str = str(row[debit_idx]).strip().replace(',', '').replace('$', '')
                        try:
                            withdrawal = float(debit_str)
                        except:
                            pass
                    
                    if credit_idx is not None and credit_idx < len(row) and row[credit_idx]:
                        credit_str = str(row[credit_idx]).strip().replace(',', '').replace('$', '')
                        try:
                            deposit = float(credit_str)
                        except:
                            pass
                    
                    # Skip if no amounts
                    if withdrawal is None and deposit is None:
                        continue
                    
                    # Parse date
                    if not date_str:
                        continue
                    
                    # Date format: "DEC31", "JAN02", "JAN 10", etc.
                    date_str_clean = date_str.replace(' ', '').upper()
                    month_match = re.match(r'([A-Z]{3})(\d{1,2})', date_str_clean)
                    
                    if month_match:
                        month_abbr = month_match.group(1)
                        day = int(month_match.group(2))
                        
                        # Determine year
                        month_num = {
                            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
                        }.get(month_abbr)
                        
                        if month_num:
                            # Use statement_end_year for dates, but if month is DEC and we're in Jan, use previous year
                            year = statement_end_year
                            if month_num == 12 and statement_start_year < statement_end_year:
                                # Could be either year, but if statement spans year boundary, DEC is likely start year
                                # For simplicity, use end year unless it's clearly in the start period
                                pass
                            
                            try:
                                date = datetime(year, month_num, day)
                                date_str_formatted = date.strftime('%Y-%m-%d')
                            except:
                                date_str_formatted = date_str
                        else:
                            date_str_formatted = date_str
                    else:
                        date_str_formatted = date_str
                    
                    # Get balance if available
                    balance = None
                    if balance_idx is not None and balance_idx < len(row) and row[balance_idx]:
                        balance_str = str(row[balance_idx]).strip().replace(',', '').replace('$', '')
                        try:
                            parsed = _parse_td_balance(balance_str)
                            if parsed is not None:
                                balance = parsed
                                # Update closing balance
                                closing_balance = balance
                        except:
                            pass
                    
                    transaction = {
                        'Date': date_str_formatted,
                        'Description': description,
                        'Withdrawals': withdrawal if withdrawal else 0.0,
                        'Deposits': deposit if deposit else 0.0,
                        'Balance': balance if balance else None
                    }
                    
                    transactions.append(transaction)
    
    # Create DataFrame from detailed transaction rows
    df = pd.DataFrame(transactions)
    
    if len(df) == 0:
        # No row-level transactions found on the pages. For some TD statements
        # (like the 0124 account with only a monthly fee), the only data is in
        # a compact summary table on page 1. Try a Camelot lattice-based
        # fallback to extract that summary as a single transaction.
        print("  WARNING: No transactions extracted from pdfplumber tables, trying Camelot summary fallback...")
        
        try:
            tables = camelot.read_pdf(
                pdf_path,
                pages="1",
                flavor="lattice",
                strip_text="\n",
            )
        except Exception as e:
            print(f"  ERROR: Camelot lattice fallback failed: {e}")
            return None, None, None, None
        
        summary_transactions = []
        
        for table in tables:
            tdf = table.df
            if tdf.shape[0] < 2 or tdf.shape[1] < 5:
                continue
            
            # Look for a header row with DESCRIPTION / DEBIT / DEPOSIT / DATE / BALANCE
            header_row = None
            for i in range(len(tdf)):
                row_text = " ".join(tdf.iloc[i].astype(str).tolist()).upper()
                if (
                    "DESCRIPTION" in row_text
                    and ("DEBIT" in row_text or "CHEQUE" in row_text)
                    and ("DEPOSIT" in row_text or "CREDIT" in row_text)
                    and "DATE" in row_text
                    and "BALANCE" in row_text
                ):
                    header_row = i
                    break
            
            if header_row is None:
                continue
            
            # Column positions in this summary layout:
            # DESCRIPTION / CHEQUE/DEBIT / DEPOSIT/CREDIT / DATE / BALANCE
            desc_col = 0
            debit_col = 1
            credit_col = 2
            date_col = 3
            balance_col = 4
            
            print(f"  Camelot fallback using summary table on page {table.page} (rows={tdf.shape[0]}, cols={tdf.shape[1]})")
            
            for row_idx in range(header_row + 1, len(tdf)):
                row = tdf.iloc[row_idx].tolist()
                raw_desc = str(row[desc_col]) if desc_col < len(row) else ""
                if not raw_desc.strip():
                    continue
                
                desc_upper = raw_desc.upper()
                clean_desc = raw_desc.strip()
                
                # Opening/closing balance from BALANCE FORWARD row, if present
                if "BALANCE FORWARD" in desc_upper:
                    bal_text = str(row[balance_col]) if balance_col < len(row) else ""
                    bal_text = bal_text.replace(",", "").replace("$", "")
                    parts = re.findall(r"-?\d+\.\d{2}", bal_text)
                    if parts:
                        try:
                            opening_balance = float(parts[0])
                            closing_balance = float(parts[-1])
                            print(f"    Fallback Opening Balance: ${opening_balance:,.2f}")
                            print(f"    Fallback Closing Balance: ${closing_balance:,.2f}")
                        except Exception:
                            pass
                    # If this row also contains a fee description, let it fall through
                    # to become a transaction; otherwise skip it.
                    if "MONTHLY PLAN FEE" not in desc_upper:
                        continue
                
                # Skip non-transaction summary rows
                if any(
                    kw in desc_upper
                    for kw in ["NEXT STATEMENT", "DEP CONTENT", "ITEMS", "UNC BATCH", "CREDITS", "DEBITS"]
                ):
                    continue
                
                withdrawal = None
                deposit = None
                
                if debit_col < len(row) and row[debit_col]:
                    try:
                        withdrawal = float(str(row[debit_col]).replace(",", "").replace("$", ""))
                    except Exception:
                        withdrawal = None
                
                if credit_col < len(row) and row[credit_col]:
                    try:
                        deposit = float(str(row[credit_col]).replace(",", "").replace("$", ""))
                    except Exception:
                        deposit = None
                
                # Skip if no amounts
                if withdrawal is None and deposit is None:
                    continue
                
                # Parse date from the DATE column, e.g. "NOV28DEC31" → take last month+day
                raw_date = str(row[date_col]) if date_col < len(row) else ""
                raw_date_clean = raw_date.replace(" ", "").upper()
                md_matches = re.findall(r"[A-Z]{3}\d{1,2}", raw_date_clean)
                date_str_formatted = raw_date
                if md_matches and statement_end_year:
                    month_day = md_matches[-1]
                    mm = re.match(r"([A-Z]{3})(\d{1,2})", month_day)
                    if mm:
                        mon = mm.group(1)
                        day = int(mm.group(2))
                        month_num = {
                            "JAN": 1,
                            "FEB": 2,
                            "MAR": 3,
                            "APR": 4,
                            "MAY": 5,
                            "JUN": 6,
                            "JUL": 7,
                            "AUG": 8,
                            "SEP": 9,
                            "OCT": 10,
                            "NOV": 11,
                            "DEC": 12,
                        }.get(mon)
                        if month_num:
                            try:
                                dt = datetime(statement_end_year, month_num, day)
                                date_str_formatted = dt.strftime("%Y-%m-%d")
                            except Exception:
                                date_str_formatted = month_day
                        else:
                            date_str_formatted = month_day
                
                # Clean up description so it doesn't look like an opening-balance row
                # to downstream filters. If the description still contains the
                # "BALANCE FORWARD" text, strip it off and keep the fee/charge part.
                if "BALANCE FORWARD" in clean_desc.upper():
                    clean_desc = re.sub(r"(?i)balance\s*forward", "", clean_desc).strip()
                    if not clean_desc:
                        clean_desc = raw_desc.strip()

                summary_transactions.append(
                    {
                        "Date": date_str_formatted,
                        "Description": clean_desc,
                        "Withdrawals": withdrawal if withdrawal is not None else 0.0,
                        "Deposits": deposit if deposit is not None else 0.0,
                        "Balance": None,
                    }
                )
        
        if not summary_transactions:
            print("  WARNING: No transactions extracted (even with Camelot fallback).")
            return None, None, None, None
        
        df = pd.DataFrame(summary_transactions)
        print(f"\n  Fallback extracted {len(df)} summary transaction(s)")
    
    print(f"\n  Extracted {len(df)} transactions")
    
    # Calculate running balance
    print("\n3. CALCULATING RUNNING BALANCE:")
    print("-" * 70)
    
    if opening_balance is not None:
        print(f"  Opening Balance: ${opening_balance:,.2f}")
        # Calculate net change per transaction
        df['Net_Change'] = df['Deposits'].fillna(0) - df['Withdrawals'].fillna(0)
        # Calculate running balance: opening + cumulative net changes
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
                print("  WARNING: Could not find closing balance")
    else:
        print("  WARNING: Could not find opening balance")
    
    return df, opening_balance, closing_balance, statement_year

def extract_td_bank_statement_camelot(pdf_path):
    """Extract transactions from TD Bank statement using Camelot"""
    print(f"\n{'='*70}")
    print(f"Extracting with CAMELOT: {Path(pdf_path).name}")
    print(f"{'='*70}\n")
    
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    statement_start_year = None
    statement_end_year = None
    
    # Extract text for metadata
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    # Extract statement period and year (same as pdfplumber version)
    print("1. EXTRACTING STATEMENT PERIOD:")
    print("-" * 70)
    
    period_match = re.search(r'Statement From - To\s+([A-Z]{3}\s?\d{1,2}/\d{2})\s*-\s*([A-Z]{3}\s?\d{1,2}/\d{2})', full_text, re.IGNORECASE)
    if not period_match:
        period_match = re.search(r'([A-Z]{3}\s?\d{1,2}/\d{2})\s*-\s*([A-Z]{3}\s?\d{1,2}/\d{2})', full_text, re.IGNORECASE)
    
    if period_match:
        start_str = period_match.group(1).strip()
        end_str = period_match.group(2).strip()
        print(f"  Statement Period: {start_str} to {end_str}")
        
        start_year_match = re.search(r'/(\d{2})$', start_str)
        end_year_match = re.search(r'/(\d{2})$', end_str)
        
        if start_year_match and end_year_match:
            start_year_short = int(start_year_match.group(1))
            end_year_short = int(end_year_match.group(1))
            statement_start_year = 2000 + start_year_short
            statement_end_year = 2000 + end_year_short
            statement_year = statement_end_year
            print(f"  Statement Start Year: {statement_start_year}")
            print(f"  Statement End Year: {statement_end_year}")
            print(f"  Primary Statement Year: {statement_year}")
    else:
        print("  WARNING: Could not extract statement period")
        statement_year = 2025
        statement_start_year = 2024
        statement_end_year = 2025
        print(f"  Using fallback year: {statement_year}")
    
    # Extract transactions using Camelot
    print("\n2. EXTRACTING TRANSACTIONS WITH CAMELOT:")
    print("-" * 70)
    
    try:
        # Try stream first
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        print(f"  Stream: Found {len(tables_stream)} table(s)")
        
        # Track opening balance from first table (page 1)
        first_table_opening = None
        
        for table_idx, table in enumerate(tables_stream):
            df_table = table.df
            
            # Debug: print table structure
            if table_idx == 0:  # Only for first table
                print(f"  Table {table_idx + 1} structure: {df_table.shape}")
                print(f"    Columns: {len(df_table.columns)}")
                print(f"    Column names: {df_table.columns.tolist()}")
                print(f"    First 10 rows:")
                for r in range(min(10, len(df_table))):
                    print(f"      Row {r}: {df_table.iloc[r].tolist()}")
            
            # Look for transaction table - check first few rows for header or transaction patterns
            header_row = None
            desc_idx = None
            debit_idx = None
            credit_idx = None
            date_idx = None
            balance_idx = None
            
            # First, try to find explicit header (check for multi-line headers too)
            for i, row in df_table.iterrows():
                if i > 20:  # Check more rows for TD bank - 7206 format
                    break
                row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in row]).upper()
                # Check if this row has header keywords (handle multi-line headers like "DEPOSIT/CREDIT\nDATE")
                has_description = 'DESCRIPTION' in row_text
                has_amount_col = 'DEBIT' in row_text or 'DEPOSIT' in row_text or 'CREDIT' in row_text or 'CHEQUE' in row_text
                has_date = 'DATE' in row_text
                
                # For Table 2 format, DATE might be in same cell as DEPOSIT/CREDIT, so check cell contents too
                # Also check for TD bank - 7206 format where everything is in one cell
                if not has_date:
                    for cell in row:
                        if pd.notna(cell):
                            cell_text = str(cell).upper().replace('\n', ' ').replace('\r', ' ')
                            if 'DATE' in cell_text:
                                has_date = True
                                break
                
                if has_description and has_amount_col and (has_date or i < 3):  # Allow DATE to be in next row for multi-line headers
                    header_row = i
                    # Parse header - check each cell individually
                    header = df_table.iloc[header_row]
                    for j, cell in enumerate(header):
                        if pd.notna(cell):
                            cell_upper = str(cell).upper().strip().replace('\n', ' ').replace('\r', ' ')
                            # Check for DESCRIPTION first
                            if 'DESCRIPTION' in cell_upper or 'PARTICULARS' in cell_upper:
                                desc_idx = j
                            # Check for TD bank - 7206 format: combined "CHEQUE/DEBIT\nDEPOSIT/CREDIT\nDATE\nBALANCE"
                            elif 'CHEQUE' in cell_upper and 'DEBIT' in cell_upper and 'DEPOSIT' in cell_upper and 'CREDIT' in cell_upper and 'DATE' in cell_upper and 'BALANCE' in cell_upper:
                                # This is the combined column for TD bank - 7206
                                debit_idx = j
                                credit_idx = j
                                date_idx = j
                                balance_idx = j
                            # Check for DEBIT (withdrawal column) - check for CHEQUE/DEBIT pattern
                            elif 'DEBIT' in cell_upper or 'DEBITS' in cell_upper or ('CHEQUE' in cell_upper and 'DEBIT' in cell_upper):
                                debit_idx = j
                            # Check for CREDIT/DEPOSIT (deposit column) - handle "DEPOSIT/CREDIT\nDATE" pattern
                            elif ('CREDIT' in cell_upper or 'DEPOSIT' in cell_upper or 'DEPOSITS' in cell_upper or 'CREDITS' in cell_upper) and 'DEBIT' not in cell_upper:
                                credit_idx = j
                                # If DATE is also in this cell (multi-line header), set date_idx to same column
                                if 'DATE' in cell_upper:
                                    date_idx = j
                            # Check for DATE (might be combined with DEPOSIT/CREDIT)
                            elif 'DATE' in cell_upper:
                                # If DATE is in same cell as DEPOSIT/CREDIT, we already set credit_idx, so set date_idx to same
                                if 'DEPOSIT' in cell_upper or 'CREDIT' in cell_upper:
                                    # DATE is combined with credit column
                                    if credit_idx is None:
                                        credit_idx = j
                                    date_idx = j
                                else:
                                    date_idx = j
                            # Check for BALANCE
                            elif 'BALANCE' in cell_upper:
                                balance_idx = j
                    
                    # If DATE wasn't found in header row, check next row (for multi-line headers)
                    if date_idx is None and header_row + 1 < len(df_table):
                        next_row = df_table.iloc[header_row + 1]
                        for j, cell in enumerate(next_row):
                            if pd.notna(cell):
                                cell_upper = str(cell).upper().strip()
                                if 'DATE' in cell_upper and date_idx is None:
                                    date_idx = j
                                    break
                    
                    break
            
            # If no explicit header found, infer from data structure
            if header_row is None:
                # Look for "BALANCE FORWARD" row which indicates start of transactions
                balance_forward_row = None
                for i, row in df_table.iterrows():
                    if i > 10:  # Only check first 10 rows
                        break
                    row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in row]).upper()
                    if 'BALANCE FORWARD' in row_text:
                        balance_forward_row = i
                        # If BALANCE FORWARD is on row 0, there's no header - use it as starting point
                        # If on row 1+, check if row 0 is a header
                        if i == 0:
                            header_row = 0  # No header row, BALANCE FORWARD is first row
                        else:
                            # Check if row 0 might be a header
                            row0_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in df_table.iloc[0]]).upper()
                            if 'DESCRIPTION' in row0_text:
                                header_row = 0
                            else:
                                header_row = i  # Use BALANCE FORWARD row as starting point
                        
                        # Check actual column count from Camelot
                        if len(df_table.columns) >= 5:
                            # For Table 1 (page 1), check the actual structure
                            # Look at BALANCE FORWARD row to determine column positions
                            bf_row_list = row.tolist()
                            # Find which column has the date (should be column 2 or 3)
                            date_col_found = None
                            for col_idx in range(len(bf_row_list)):
                                if col_idx != 0:  # Skip description
                                    cell = bf_row_list[col_idx] if col_idx < len(bf_row_list) else None
                                    if pd.notna(cell):
                                        cell_str = str(cell).strip()
                                        # Check if this looks like a date (AUG29, SEP02, etc.)
                                        if re.search(r'[A-Z]{3}\d{1,2}', cell_str.upper()):
                                            date_col_found = col_idx
                                            break
                            
                            desc_idx = 0
                            debit_idx = 1
                            if date_col_found == 2:
                                # DATE is in column 2, no separate CREDIT column
                                # Deposits have amount+date in column 2 (e.g., "4,153.05 SEP05")
                                credit_idx = None
                                date_idx = 2
                            else:
                                # Standard 5-column format: DESC(0), DEBIT(1), CREDIT(2), DATE(3), BALANCE(4)
                                credit_idx = 2
                                date_idx = 3 if date_col_found is None else date_col_found
                            balance_idx = 4
                        elif len(df_table.columns) == 4:
                            # Camelot 4-column format: Check if there's a header row above BALANCE FORWARD
                            # Look at row before BALANCE FORWARD to see if it has column headers
                            if i > 0:
                                prev_row = df_table.iloc[i - 1]
                                prev_row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in prev_row]).upper()
                                # Check if previous row has headers
                                if 'DESCRIPTION' in prev_row_text or 'DEBIT' in prev_row_text or 'DEPOSIT' in prev_row_text:
                                    header_row = i - 1
                                    # Check for TD bank - 7206 format: DESCRIPTION in col 2, combined data in col 3
                                    # Look for "CHEQUE/DEBIT\nDEPOSIT/CREDIT\nDATE\nBALANCE" pattern in column 3
                                    combined_col = None
                                    for j, cell in enumerate(prev_row):
                                        if pd.notna(cell):
                                            cell_upper = str(cell).upper().strip()
                                            if 'DESCRIPTION' in cell_upper:
                                                desc_idx = j
                                            elif 'CHEQUE' in cell_upper and 'DEBIT' in cell_upper and 'DEPOSIT' in cell_upper and 'CREDIT' in cell_upper and 'DATE' in cell_upper and 'BALANCE' in cell_upper:
                                                # This is the combined column (TD bank - 7206 format)
                                                combined_col = j
                                                # All transaction data is in this column
                                                debit_idx = j
                                                credit_idx = j
                                                date_idx = j
                                                balance_idx = j
                                            elif 'DEBIT' in cell_upper and combined_col is None:
                                                debit_idx = j
                                            elif ('CREDIT' in cell_upper or 'DEPOSIT' in cell_upper) and combined_col is None:
                                                credit_idx = j
                                            elif 'DATE' in cell_upper and combined_col is None:
                                                date_idx = j
                                            elif 'BALANCE' in cell_upper:
                                                balance_idx = j
                            # If no header found, use default 4-column layout: DESC(0), AMOUNT(1), DATE(2), BALANCE(3)
                            if desc_idx is None:
                                desc_idx = 0
                                date_idx = 2
                                balance_idx = 3
                                # Column 1 is the amount column - check if it's typically debit or credit
                                # For TD Bank, if there's only one amount column, it's usually DEBIT (withdrawals)
                                # Credits/deposits would be empty in this column
                                debit_idx = 1
                                credit_idx = None  # No separate credit column
                        break
            
            # Final fallback: infer from column count and data patterns
            if header_row is None or desc_idx is None:
                # Check if table has transaction-like data
                for i, row in df_table.iterrows():
                    if i > 5:
                        break
                    row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in row])
                    # Check for date pattern
                    if re.search(r'[A-Z]{3}\s?\d{1,2}', row_text):
                        header_row = 0
                        # TD Bank has 5 columns: DESC(0), DEBIT(1), CREDIT(2), DATE(3), BALANCE(4)
                        if len(df_table.columns) >= 5:
                            desc_idx = 0
                            debit_idx = 1
                            credit_idx = 2
                            date_idx = 3
                            balance_idx = 4
                        elif len(df_table.columns) >= 4:
                            desc_idx = 0
                            date_idx = 2
                            balance_idx = 3
                        break
            
            # If still no header found, try to detect from Table 2 format (4 columns with header on row 0)
            # This handles cases where header is on row 0 and data starts on row 1
            if header_row is None or desc_idx is None:
                # Check if row 0 looks like a header row
                if len(df_table) > 0:
                    first_row = df_table.iloc[0]
                    first_row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in first_row]).upper()
                    if 'DESCRIPTION' in first_row_text and ('DEBIT' in first_row_text or 'CHEQUE' in first_row_text or 'DEPOSIT' in first_row_text):
                        header_row = 0
                        # Parse this header row
                        for j, cell in enumerate(first_row):
                            if pd.notna(cell):
                                cell_upper = str(cell).upper().strip().replace('\n', ' ').replace('\r', ' ')
                                if 'DESCRIPTION' in cell_upper:
                                    desc_idx = j
                                elif 'DEBIT' in cell_upper or 'CHEQUE' in cell_upper:
                                    debit_idx = j
                                elif 'DEPOSIT' in cell_upper or 'CREDIT' in cell_upper:
                                    credit_idx = j
                                    # DATE might be in same cell (multi-line header like "DEPOSIT/CREDIT\nDATE")
                                    if 'DATE' in cell_upper:
                                        date_idx = j
                                elif 'DATE' in cell_upper:
                                    date_idx = j
                                elif 'BALANCE' in cell_upper:
                                    balance_idx = j
                        # If DATE not found, check if it's in the credit column (multi-line header)
                        if date_idx is None and credit_idx is not None:
                            date_idx = credit_idx  # DATE is in same column as DEPOSIT/CREDIT
                        # If still no date_idx, use default based on column count
                        if date_idx is None:
                            if len(df_table.columns) == 4:
                                # 4-column format: DESC(0), DEBIT(1), CREDIT/DATE(2), BALANCE(3)
                                date_idx = credit_idx if credit_idx is not None else 2
                            elif len(df_table.columns) == 5:
                                date_idx = 3  # Default position for 5-column format
                        # Ensure we have balance_idx for 4-column format
                        if balance_idx is None and len(df_table.columns) == 4:
                            balance_idx = 3
                        # Ensure we have debit_idx for 4-column format
                        if debit_idx is None and len(df_table.columns) == 4:
                            debit_idx = 1
                        # CRITICAL: Ensure date_idx is set for 4-column format (DATE is in column 2 with CREDIT)
                        if date_idx is None and len(df_table.columns) == 4:
                            date_idx = 2
            
            # Final check - if we still don't have required indices, try one more time with simpler detection
            if header_row is None or desc_idx is None:
                # Last resort: assume standard TD Bank format based on column count
                if len(df_table.columns) >= 4 and len(df_table) > 1:
                    # Check if row 0 or row 1 has transaction-like data
                    for check_row in [0, 1]:
                        if check_row < len(df_table):
                            row = df_table.iloc[check_row]
                            row_text = ' '.join([str(cell) if pd.notna(cell) else '' for cell in row]).upper()
                            # If this looks like a header, use it
                            if 'DESCRIPTION' in row_text or 'BALANCE FORWARD' in row_text:
                                if 'DESCRIPTION' in row_text:
                                    header_row = check_row
                                # Use default column positions based on column count
                                if len(df_table.columns) == 4:
                                    desc_idx = 0
                                    debit_idx = 1
                                    credit_idx = 2  # DEPOSIT/CREDIT column
                                    date_idx = 2  # DATE is in same column as CREDIT
                                    balance_idx = 3
                                elif len(df_table.columns) == 5:
                                    desc_idx = 0
                                    debit_idx = 1
                                    credit_idx = 2
                                    date_idx = 3
                                    balance_idx = 4
                                elif len(df_table.columns) == 6:
                                    # 6-column format: DESC(0), DEBIT(1), CREDIT(2), DATE(3), (empty 4), BALANCE(5)
                                    desc_idx = 0
                                    debit_idx = 1
                                    credit_idx = 2
                                    date_idx = 3
                                    balance_idx = 5
                                break
            
            if header_row is None or desc_idx is None or date_idx is None:
                print(f"  Table {table_idx + 1}: Could not determine structure (cols={len(df_table.columns)}, rows={len(df_table)})")
                print(f"    header_row={header_row}, desc_idx={desc_idx}, date_idx={date_idx}")
                # Print first few rows for debugging
                if len(df_table) > 0:
                    print(f"    First 3 rows:")
                    for r in range(min(3, len(df_table))):
                        print(f"      Row {r}: {df_table.iloc[r].tolist()}")
                # Don't skip - try to use defaults based on column count
                if len(df_table.columns) >= 4 and len(df_table) > 1:
                    print(f"    Attempting to use default column positions...")
                    header_row = 0
                    if len(df_table.columns) == 4:
                        desc_idx = 0
                        debit_idx = 1
                        credit_idx = 2
                        date_idx = 2  # DATE in same column as CREDIT
                        balance_idx = 3
                    elif len(df_table.columns) == 5:
                        desc_idx = 0
                        debit_idx = 1
                        credit_idx = 2
                        date_idx = 3
                        balance_idx = 4
                    elif len(df_table.columns) == 6:
                        # 6-column format: DESC(0), DEBIT(1), CREDIT(2), DATE(3), (empty 4), BALANCE(5)
                        desc_idx = 0
                        debit_idx = 1
                        credit_idx = 2
                        date_idx = 3
                        balance_idx = 5
                    print(f"    Using defaults: DESC={desc_idx}, DEBIT={debit_idx}, CREDIT={credit_idx}, DATE={date_idx}, BALANCE={balance_idx}")
                else:
                    continue
            
            # Fix balance_idx for 6-column format if detected
            if len(df_table.columns) == 6 and balance_idx == 4:
                # 6-column format has balance in column 5, not 4
                balance_idx = 5
                print(f"    Adjusted balance_idx to 5 for 6-column format")
            
            print(f"  Table {table_idx + 1} (page {table.page}): Using row {header_row} as start")
            print(f"    Columns: DESC={desc_idx}, DEBIT={debit_idx}, CREDIT={credit_idx}, DATE={date_idx}, BALANCE={balance_idx}")

            # Skip malformed/noise tables (e.g., cheque image pages) before row access.
            if desc_idx is None or date_idx is None:
                print("    Skipping table: missing required description/date columns")
                continue
            
            # First, extract opening balance from BALANCE FORWARD row if it exists
            # For first table, this is the statement opening balance
            # For subsequent tables, this is a continuation (don't overwrite opening_balance)
            if header_row is not None and header_row < len(df_table):
                bf_row = df_table.iloc[header_row]
                bf_description = str(bf_row.iloc[desc_idx]).strip() if desc_idx < len(bf_row) and pd.notna(bf_row.iloc[desc_idx]) else ""
                if 'BALANCE FORWARD' in bf_description.upper():
                    # Extract balance from this row
                    balance_str = None
                    # Try balance column first
                    if balance_idx is not None and balance_idx < len(bf_row):
                        cell = bf_row.iloc[balance_idx]
                        if pd.notna(cell):
                            cell_str = str(cell).strip()
                            # For TD bank - 7206 format, balance might be on second line: "DATE\nBALANCE"
                            if '\n' in cell_str:
                                lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                                # Look for balance (number without date pattern) in any line
                                for line in lines:
                                    if re.search(r'\d+[,.]?\d*\.?\d{0,2}', line) and not re.search(r'[A-Z]{3}\d{1,2}', line.upper()):
                                        balance_str = line
                                        break
                                # If not found, try last line (usually balance)
                                if not balance_str and len(lines) > 0:
                                    balance_str = lines[-1]
                            else:
                                balance_str = cell_str
                    
                    # If not found, check all columns for a number that looks like a balance
                    if not balance_str or not re.search(r'\d+[,.]?\d*\.?\d{0,2}', balance_str):
                        for col_idx in range(len(bf_row)):
                            if col_idx == desc_idx:  # Skip description column
                                continue
                            cell = bf_row.iloc[col_idx]
                            if pd.notna(cell):
                                cell_str = str(cell).strip()
                                # For newline-separated format, check each line
                                if '\n' in cell_str:
                                    lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                                    for line in lines:
                                        # Look for a number with commas and/or decimal (balance format) without date
                                        if re.search(r'\d+[,.]?\d*\.?\d{0,2}', line) and not re.search(r'[A-Z]{3}\d{1,2}', line.upper()):
                                            balance_str = line
                                            break
                                else:
                                    # Look for a number with commas and/or decimal (balance format)
                                    if re.search(r'\d+[,.]?\d*\.?\d{0,2}', cell_str) and not re.search(r'[A-Z]{3}', cell_str):
                                        # This looks like a balance amount
                                        balance_str = cell_str
                                        break
                                if balance_str:
                                    break
                    
                    if balance_str:
                        balance_str = balance_str.replace(',', '').replace('$', '').strip()
                        try:
                            parsed = _parse_td_balance(balance_str)
                            if parsed is None:
                                raise ValueError("balance parse returned None")
                            bf_balance = parsed
                            # For first table (page 1), this is the opening balance
                            # For subsequent tables (page 2+), this is the continuation balance - don't overwrite
                            if table_idx == 0 or opening_balance is None:
                                opening_balance = bf_balance
                                first_table_opening = bf_balance
                                print(f"    Opening Balance from BALANCE FORWARD: ${opening_balance:,.2f}")
                            else:
                                # This is a continuation from previous page - don't overwrite opening balance
                                # Also don't use this as closing balance - it's just a continuation marker
                                print(f"    Continuation Balance from BALANCE FORWARD: ${bf_balance:,.2f} (page {table.page}, not using as opening or closing)")
                        except Exception as e:
                            print(f"    Warning: Could not parse balance '{balance_str}': {e}")
            
            # Parse transactions (start after BALANCE FORWARD row)
            # For Table 1 where BALANCE FORWARD is on row 0, start from row 1
            # For Table 2 where header is on row 0 and BALANCE FORWARD is on row 1, start from row 2
            start_row = header_row + 1
            # If BALANCE FORWARD was on header_row, we already extracted it, so start from next row
            # But if header_row was the actual header (not BALANCE FORWARD), check if row after header is BALANCE FORWARD
            if header_row < len(df_table):
                check_row = df_table.iloc[header_row]
                check_desc = str(check_row.iloc[desc_idx]).strip() if desc_idx < len(check_row) and pd.notna(check_row.iloc[desc_idx]) else ""
                if 'BALANCE FORWARD' not in check_desc.upper() and header_row + 1 < len(df_table):
                    # Header row is not BALANCE FORWARD, check next row
                    next_row = df_table.iloc[header_row + 1]
                    next_desc = str(next_row.iloc[desc_idx]).strip() if desc_idx < len(next_row) and pd.notna(next_row.iloc[desc_idx]) else ""
                    if 'BALANCE FORWARD' in next_desc.upper():
                        # Extract opening balance from this BALANCE FORWARD row
                        balance_str = None
                        if balance_idx is not None and balance_idx < len(next_row):
                            cell = next_row.iloc[balance_idx]
                            if pd.notna(cell):
                                cell_str = str(cell).strip()
                                # For TD bank - 7206 format, balance might be on second line: "DATE\nBALANCE"
                                if '\n' in cell_str:
                                    lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                                    for line in lines:
                                        if re.search(r'\d+[,.]?\d*\.?\d{0,2}', line) and not re.search(r'[A-Z]{3}\d{1,2}', line.upper()):
                                            balance_str = line
                                            break
                                    if not balance_str and len(lines) > 0:
                                        balance_str = lines[-1]
                                else:
                                    balance_str = cell_str
                        
                        if balance_str:
                            balance_str = balance_str.replace(',', '').replace('$', '').strip()
                            try:
                                parsed = _parse_td_balance(balance_str)
                                if parsed is None:
                                    raise ValueError("balance parse returned None")
                                bf_balance = parsed
                                if table_idx == 0 or opening_balance is None:
                                    opening_balance = bf_balance
                                    print(f"    Opening Balance from BALANCE FORWARD (row {header_row + 1}): ${opening_balance:,.2f}")
                            except:
                                pass
                        
                        start_row = header_row + 2  # Skip header and BALANCE FORWARD rows
            
            transactions_before_table = len(transactions)
            print(f"    Starting transaction extraction from row {start_row} (total rows: {len(df_table)})")
            rows_processed = 0
            rows_skipped = 0
            
            for row_idx in range(start_row, len(df_table)):
                row = df_table.iloc[row_idx]
                rows_processed += 1
                
                # Initialize variables at the start of each iteration
                withdrawal = None
                deposit = None
                
                description = str(row.iloc[desc_idx]).strip() if desc_idx < len(row) and pd.notna(row.iloc[desc_idx]) else ""
                
                # For 6-column format, amount might be in DESCRIPTION column with newline (e.g., "UI251 TFR-TO C/C\n300.00")
                if desc_idx is not None and desc_idx < len(row) and pd.notna(row.iloc[desc_idx]):
                    desc_cell = str(row.iloc[desc_idx]).strip()
                    if '\n' in desc_cell:
                        lines = desc_cell.split('\n')
                        if len(lines) >= 2:
                            # Last line might be amount
                            last_line = lines[-1].strip()
                            amount_match = re.search(r'([\d,]+\.?\d{0,2})', last_line, re.IGNORECASE)
                            if amount_match:
                                amount_str = amount_match.group(1).replace(',', '').replace('$', '')
                                # Check if it's a withdrawal based on description
                                desc_upper = description.upper()
                                if 'TFR-TO' in desc_upper or 'WITHDRAWAL' in desc_upper or 'DEBIT' in desc_upper:
                                    try:
                                        withdrawal = float(amount_str)
                                    except:
                                        pass
                                else:
                                    try:
                                        deposit = float(amount_str)
                                    except:
                                        pass
                            # Update description to first line only
                            description = lines[0].strip()
                
                # Try to get date - check if date_idx is valid
                date_str = ""
                if date_idx is not None and date_idx < len(row):
                    date_cell = row.iloc[date_idx]
                    if pd.notna(date_cell):
                        date_cell_str = str(date_cell).strip()
                        # For TD bank - 7206 format, date can be in different formats:
                        # 1. "AMOUNT DATE\nBALANCE" - date in first line
                        # 2. "AMOUNT\nDATE\nBALANCE" - date in second line
                        # 3. "AMOUNT DATE" - combined in date column (6-column format)
                        if '\n' in date_cell_str:
                            lines = [line.strip() for line in date_cell_str.split('\n') if line.strip()]
                            if len(lines) >= 1:
                                first_line = lines[0]
                                # Check if first line has date
                                date_match = re.search(r'([A-Z]{3}\d{1,2})', first_line, re.IGNORECASE)
                                if date_match:
                                    date_str = date_match.group(1)
                                elif len(lines) >= 2:
                                    # Date might be on second line
                                    second_line = lines[1]
                                    date_match = re.search(r'([A-Z]{3}\d{1,2})', second_line, re.IGNORECASE)
                                    if date_match:
                                        date_str = date_match.group(1)
                        else:
                            # No newlines - could be "AMOUNT DATE" or just "DATE"
                            date_match = re.search(r'([A-Z]{3}\d{1,2})', date_cell_str, re.IGNORECASE)
                            if date_match:
                                date_str = date_match.group(1)
                                # If there's also an amount in this cell, extract it
                                amount_match = re.search(r'([\d,]+\.?\d{0,2})\s*([A-Z]{3}\d{1,2})', date_cell_str, re.IGNORECASE)
                                if amount_match and deposit is None and withdrawal is None:
                                    amount_str = amount_match.group(1).replace(',', '').replace('$', '')
                                    try:
                                        deposit = float(amount_str)
                                    except:
                                        pass
                            else:
                                date_str = date_cell_str
                    # If empty, try to find date in other columns (for Table 1, date might be in column 2 or 3)
                    if not date_str and rows_processed <= 3:
                        # Debug: check all columns for date pattern
                        for col_idx in range(len(row)):
                            if col_idx != desc_idx:
                                cell = row.iloc[col_idx] if col_idx < len(row) else None
                                if pd.notna(cell):
                                    cell_str = str(cell).strip()
                                    # Check for date pattern in cell (handle newlines)
                                    if '\n' in cell_str:
                                        lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                                        for line in lines:
                                            date_match = re.search(r'([A-Z]{3}\d{1,2})', line, re.IGNORECASE)
                                            if date_match:
                                                date_str = date_match.group(1)
                                                if rows_processed <= 3:
                                                    print(f"        Found date in column {col_idx} instead of {date_idx}: '{date_str}'")
                                                # Update date_idx for this table
                                                if date_idx != col_idx:
                                                    date_idx = col_idx
                                                break
                                    elif re.search(r'[A-Z]{3}\d{1,2}', cell_str.upper()):
                                        date_str = cell_str
                                        if rows_processed <= 3:
                                            print(f"        Found date in column {col_idx} instead of {date_idx}: '{date_str}'")
                                        # Update date_idx for this table
                                        if date_idx != col_idx:
                                            date_idx = col_idx
                                        break
                                if date_str:
                                    break
                
                # Debug first few rows
                if rows_processed <= 5:
                    print(f"      Row {row_idx}: desc='{description[:30]}', date='{date_str}', date_idx={date_idx}, row_cols={len(row)}")
                    print(f"        Row data: {row.tolist()}")
                    print(f"        desc_idx={desc_idx}, debit_idx={debit_idx}, credit_idx={credit_idx}, balance_idx={balance_idx}")
                
                # Skip empty rows
                if not description and not date_str:
                    rows_skipped += 1
                    continue
                
                # Check for opening balance
                if 'BALANCE FORWARD' in description.upper():
                    # Opening balance might be in balance column or any column with a number
                    balance_str = None
                    
                    # First try balance column
                    if balance_idx is not None and balance_idx < len(row):
                        cell = row.iloc[balance_idx]
                        if pd.notna(cell):
                            cell_str = str(cell).strip()
                            # For TD bank - 7206 format, balance might be on second line: "DATE\nBALANCE"
                            if '\n' in cell_str:
                                lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                                # Look for balance (number without date pattern) in any line
                                for line in lines:
                                    if re.search(r'\d+[,.]?\d*\.?\d{0,2}', line) and not re.search(r'[A-Z]{3}\d{1,2}', line.upper()):
                                        balance_str = line
                                        break
                                # If not found, try last line (usually balance)
                                if not balance_str and len(lines) > 0:
                                    balance_str = lines[-1]
                            else:
                                balance_str = cell_str
                    
                    # If not found, check all columns for a number that looks like a balance
                    if not balance_str or not re.search(r'\d+[,.]?\d*\.?\d{0,2}', balance_str):
                        for col_idx in range(len(row)):
                            if col_idx == desc_idx:  # Skip description column
                                continue
                            cell = row.iloc[col_idx]
                            if pd.notna(cell):
                                cell_str = str(cell).strip()
                                # For newline-separated format, check each line
                                if '\n' in cell_str:
                                    lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                                    for line in lines:
                                        # Look for a number with commas and/or decimal (balance format) without date
                                        if re.search(r'\d+[,.]?\d*\.?\d{0,2}', line) and not re.search(r'[A-Z]{3}\d{1,2}', line.upper()):
                                            balance_str = line
                                            break
                                else:
                                    # Look for a number with commas and/or decimal (balance format)
                                    if re.search(r'\d+[,.]?\d*\.?\d{0,2}', cell_str) and not re.search(r'[A-Z]{3}', cell_str):
                                        # This looks like a balance amount
                                        balance_str = cell_str
                                        break
                    
                    if balance_str:
                        balance_str = balance_str.replace(',', '').replace('$', '').strip()
                        try:
                            parsed = _parse_td_balance(balance_str)
                            if parsed is not None:
                                opening_balance = parsed
                                print(f"    Opening Balance: ${opening_balance:,.2f}")
                        except Exception as e:
                            print(f"    Warning: Could not parse balance '{balance_str}': {e}")
                    else:
                        print(f"    Warning: BALANCE FORWARD found but could not extract balance from row: {row.tolist()}")
                    continue
                
                # Extract amounts FIRST (before checking if it's a summary row)
                # Note: withdrawal and deposit are already initialized at the start of the loop
                
                # Extract amounts based on column positions from header
                # If we have separate debit and credit columns, use them directly
                if debit_idx is not None and credit_idx is not None and debit_idx != credit_idx:
                    # Separate debit and credit columns - use column positions
                    if debit_idx < len(row) and pd.notna(row.iloc[debit_idx]):
                        debit_str = str(row.iloc[debit_idx]).strip().replace(',', '').replace('$', '')
                        if debit_str:  # Only if not empty
                            try:
                                withdrawal = float(debit_str)
                            except:
                                pass
                    
                    if credit_idx < len(row) and pd.notna(row.iloc[credit_idx]):
                        credit_cell_str = str(row.iloc[credit_idx]).strip()
                        # Check if credit column has combined amount+date (e.g., "10.00 SEP29")
                        combined_match = re.search(r'([\d,]+\.?\d{0,2})\s*([A-Z]{3}\d{1,2})', credit_cell_str, re.IGNORECASE)
                        if combined_match:
                            # Extract amount from combined string
                            amount_str = combined_match.group(1).replace(',', '').replace('$', '')
                            try:
                                deposit = float(amount_str)
                            except:
                                pass
                        else:
                            # Try to parse as plain number
                            credit_str = credit_cell_str.replace(',', '').replace('$', '')
                            if credit_str:  # Only if not empty
                                try:
                                    deposit = float(credit_str)
                                except:
                                    pass
                elif debit_idx is not None and credit_idx is not None and debit_idx == credit_idx:
                    # Same column for debit and credit - this is TD bank - 7206 format
                    # Column can contain different formats:
                    # 1. "AMOUNT DATE\nBALANCE" (e.g., "100.00 FEB03\n305.17")
                    # 2. "AMOUNT\nDATE\nBALANCE" (e.g., "1,000.00\nNOV18\n67.73")
                    if credit_idx < len(row) and pd.notna(row.iloc[credit_idx]):
                        cell_str = str(row.iloc[credit_idx]).strip()
                        # Split by newlines to get amount, date, and balance
                        lines = [line.strip() for line in cell_str.split('\n') if line.strip()]
                        
                        if len(lines) >= 2:
                            # Check if first line has amount+date combined
                            first_line = lines[0]
                            combined_match = re.search(r'([\d,]+\.?\d{0,2})\s*([A-Z]{3}\d{1,2})', first_line, re.IGNORECASE)
                            if combined_match:
                                # Format 1: "AMOUNT DATE\nBALANCE"
                                amount_str = combined_match.group(1).replace(',', '').replace('$', '')
                                date_part = combined_match.group(2)
                                if not date_str or date_str == '':
                                    date_str = date_part
                                try:
                                    deposit = float(amount_str)
                                except:
                                    pass
                            else:
                                # Format 2: "AMOUNT\nDATE\nBALANCE" - amount and date on separate lines
                                # First line should be amount
                                amount_match = re.search(r'([\d,]+\.?\d{0,2})', first_line, re.IGNORECASE)
                                if amount_match:
                                    amount_str = amount_match.group(1).replace(',', '').replace('$', '')
                                    # Second line should be date
                                    if len(lines) >= 2:
                                        second_line = lines[1]
                                        date_match = re.search(r'([A-Z]{3}\d{1,2})', second_line, re.IGNORECASE)
                                        if date_match:
                                            if not date_str or date_str == '':
                                                date_str = date_match.group(1)
                                            # Check description to determine if withdrawal or deposit
                                            # "TFR-TO" usually means withdrawal, "TFR-FR" or "PTS FRM" means deposit
                                            desc_upper = description.upper()
                                            if 'TFR-TO' in desc_upper or 'WITHDRAWAL' in desc_upper or 'DEBIT' in desc_upper:
                                                try:
                                                    withdrawal = float(amount_str)
                                                except:
                                                    pass
                                            else:
                                                try:
                                                    deposit = float(amount_str)
                                                except:
                                                    pass
                        elif len(lines) == 1:
                            # Only one line - could be "AMOUNT DATE" or just "DATE"
                            first_line = lines[0]
                            combined_match = re.search(r'([\d,]+\.?\d{0,2})\s*([A-Z]{3}\d{1,2})', first_line, re.IGNORECASE)
                            if combined_match:
                                amount_str = combined_match.group(1).replace(',', '').replace('$', '')
                                date_part = combined_match.group(2)
                                if not date_str or date_str == '':
                                    date_str = date_part
                                try:
                                    deposit = float(amount_str)
                                except:
                                    pass
                            elif re.search(r'^[A-Z]{3}\d{1,2}$', first_line, re.IGNORECASE):
                                # Just a date
                                if not date_str or date_str == '':
                                    date_str = first_line
                        
                        # If still no amount found, try to parse the whole cell
                        if deposit is None and withdrawal is None:
                            combined_match = re.search(r'([\d,]+\.?\d{0,2})\s*([A-Z]{3}\d{1,2})', cell_str, re.IGNORECASE)
                            if combined_match:
                                amount_str = combined_match.group(1).replace(',', '').replace('$', '')
                                date_part = combined_match.group(2)
                                if not date_str or date_str == '':
                                    date_str = date_part
                                try:
                                    deposit = float(amount_str)
                                except:
                                    pass
                elif debit_idx is not None and credit_idx is None:
                    # Only debit column exists (4-column format where column 1 is debit)
                    # OR 6-column format where DESCRIPTION column can have amount with newline
                    # Check debit column first (or DESCRIPTION column if debit_idx == desc_idx)
                    debit_cell = row.iloc[debit_idx] if debit_idx < len(row) else None
                    debit_str = str(debit_cell).strip().replace(',', '').replace('$', '') if pd.notna(debit_cell) and debit_cell != '' else ''
                    
                    # For 6-column format, debit_idx might be same as desc_idx, and amount is in description with newline
                    if debit_idx == desc_idx and '\n' in str(debit_cell) if pd.notna(debit_cell) else False:
                        # Amount is in description column with newline (e.g., "UI251 TFR-TO C/C\n300.00")
                        lines = str(debit_cell).split('\n')
                        if len(lines) >= 2:
                            last_line = lines[-1].strip()
                            amount_match = re.search(r'([\d,]+\.?\d{0,2})', last_line, re.IGNORECASE)
                            if amount_match:
                                debit_str = amount_match.group(1).replace(',', '').replace('$', '')
                    
                    if debit_str:  # Debit column has amount - it's a withdrawal
                        try:
                            withdrawal = float(debit_str)
                        except:
                            pass
                    else:
                        # Debit column is empty - check if date column has combined amount+date (deposit)
                        # Pattern: "3,550.28 JAN10" or "3550.28JAN10" or "100.00 SEP02"
                        if date_idx is not None and date_idx < len(row):
                            date_cell = row.iloc[date_idx]
                            if pd.notna(date_cell):
                                date_cell_str = str(date_cell).strip()
                                # Look for amount followed by date pattern
                                combined_match = re.search(r'([\d,]+\.?\d{0,2})\s*([A-Z]{3}\d{1,2})', date_cell_str, re.IGNORECASE)
                                if combined_match:
                                    # Found amount in date column - this is a deposit
                                    amount_str = combined_match.group(1).replace(',', '')
                                    try:
                                        deposit = float(amount_str)
                                    except:
                                        pass
                elif credit_idx is not None and debit_idx is None:
                    # Only credit column exists (or 6-column format where credit_idx is set but debit_idx is None)
                    # For 6-column format, amounts can be in:
                    # 1. DESCRIPTION column with newline (withdrawals) - already handled above
                    # 2. DATE column with combined amount+date (deposits)
                    # 3. CREDIT column (if it has a value)
                    
                    # First check credit column
                    if credit_idx < len(row) and pd.notna(row.iloc[credit_idx]):
                        amount_str = str(row.iloc[credit_idx]).strip().replace(',', '').replace('$', '')
                        if amount_str:  # Only if not empty
                            try:
                                deposit = float(amount_str)
                            except:
                                pass
                    
                    # If no amount found in credit column, check date column for combined amount+date (6-column format)
                    if deposit is None and withdrawal is None and date_idx is not None and date_idx < len(row):
                        date_cell = row.iloc[date_idx]
                        if pd.notna(date_cell):
                            date_cell_str = str(date_cell).strip()
                            # Look for amount followed by date pattern (e.g., "100.00 SEP02")
                            combined_match = re.search(r'([\d,]+\.?\d{0,2})\s*([A-Z]{3}\d{1,2})', date_cell_str, re.IGNORECASE)
                            if combined_match:
                                # Found amount in date column - this is likely a deposit
                                amount_str = combined_match.group(1).replace(',', '')
                                try:
                                    deposit = float(amount_str)
                                except:
                                    pass
                elif debit_idx == credit_idx and debit_idx is not None:
                    # Same column for both - this shouldn't happen if header detection worked, but handle it
                    if debit_idx < len(row) and pd.notna(row.iloc[debit_idx]):
                        amount_str = str(row.iloc[debit_idx]).strip().replace(',', '').replace('$', '')
                        if amount_str:
                            try:
                                # Default to withdrawal if we can't determine from header
                                withdrawal = float(amount_str)
                            except:
                                pass
                
                # Skip summary rows (but NOT transaction rows like "MONTHLY PLAN FEE" which is a real transaction)
                # Filter out summary/total rows more aggressively
                description_upper = description.upper()
                
                # Check for summary row patterns - these should always be skipped
                summary_patterns = [
                    description_upper.startswith('CREDITS'),
                    description_upper.startswith('DEBITS'),
                    'MONTHLY AVER' in description_upper and 'CR. BAL.' in description_upper,
                    'MONTHLY MIN' in description_upper and 'BAL.' in description_upper,
                    'DEP CONTENT' in description_upper,
                    'NEXT STATEMENT' in description_upper,
                    'ITEMS' in description_upper and 'UNC BATCH' in description_upper,
                    'LIMIT:' in description_upper,
                    description_upper == 'TOTAL' or description_upper.startswith('TOTAL '),
                    # Check if description is just a number (like row numbers in summary)
                    description_upper.strip().isdigit() and len(description_upper.strip()) <= 3,
                ]
                
                is_summary = any(summary_patterns)
                
                # Additional check: if description contains "CHQS ENCLOSED" or similar, it's a summary
                if 'CHQS ENCLOSED' in description_upper or 'ENCLOSED' in description_upper and 'CHQ' in description_upper:
                    is_summary = True
                
                if is_summary:
                    rows_skipped += 1
                    if rows_processed <= 5:  # Debug first few
                        print(f"        Skipped: summary row (desc='{description[:30]}')")
                    continue
                
                # Don't skip "MONTHLY PLAN FEE" or other fee transactions - they have amounts and are real transactions
                
                # Skip if no amounts (after checking for summary rows)
                if withdrawal is None and deposit is None:
                    rows_skipped += 1
                    if rows_processed <= 5:  # Debug first few
                        print(f"        Skipped: no amounts found (desc='{description[:30]}', date='{date_str}')")
                        print(f"          debit_idx={debit_idx}, credit_idx={credit_idx}, date_idx={date_idx}")
                        print(f"          Row data: {row.tolist()}")
                    continue
                
                # Parse date - check if amount is combined with date (e.g., "3,550.28 JAN10")
                if not date_str:
                    continue
                
                # Skip if date looks like a header or invalid (e.g., "No.", "Amount", "Date")
                date_str_upper = date_str.upper().strip()
                invalid_date_patterns = ['NO.', 'AMOUNT', 'DATE', 'REF', 'NUMBER', '#' ]
                if any(pattern in date_str_upper for pattern in invalid_date_patterns) and len(date_str_upper) < 10:
                    rows_skipped += 1
                    if rows_processed <= 5:
                        print(f"        Skipped: invalid date pattern (date='{date_str}')")
                    continue
                
                # Check if date cell contains an amount (deposits often have amount in date column for 4-col format)
                date_amount = None
                date_str_clean = date_str.replace(' ', '').upper()
                
                # Pattern: amount followed by date (e.g., "3,550.28JAN10" or "3550.28 JAN10")
                combined_match = re.search(r'([\d,]+\.?\d{0,2})\s*([A-Z]{3}\d{1,2})', date_str, re.IGNORECASE)
                if combined_match:
                    # Extract amount and date separately
                    date_amount_str = combined_match.group(1).replace(',', '')
                    try:
                        date_amount = float(date_amount_str)
                        # If we found an amount in the date column and debit column is empty, this is likely a deposit
                        if date_amount and (debit_idx is None or debit_idx >= len(row) or not pd.notna(row.iloc[debit_idx]) or str(row.iloc[debit_idx]).strip() == ''):
                            deposit = date_amount
                            # Update date_str to just the date part
                            date_str = combined_match.group(2)
                    except:
                        pass
                
                # If no combined pattern, try to extract just the date
                if not combined_match:
                    date_str_clean = date_str.replace(' ', '').upper()
                else:
                    date_str_clean = date_str.replace(' ', '').upper()
                
                month_match = re.match(r'([A-Z]{3})(\d{1,2})', date_str_clean)
                
                if month_match:
                    month_abbr = month_match.group(1)
                    day = int(month_match.group(2))
                    
                    month_num = {
                        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
                    }.get(month_abbr)
                    
                    if month_num:
                        year = statement_end_year
                        try:
                            date = datetime(year, month_num, day)
                            date_str_formatted = date.strftime('%Y-%m-%d')
                        except:
                            date_str_formatted = date_str
                    else:
                        date_str_formatted = date_str
                else:
                    date_str_formatted = date_str
                
                # Get balance (update closing balance with each transaction that has a balance)
                balance = None
                if balance_idx is not None and balance_idx < len(row) and pd.notna(row.iloc[balance_idx]):
                    balance_cell = row.iloc[balance_idx]
                    balance_cell_str = str(balance_cell).strip()
                    
                    # For TD bank - 7206 format, balance might be on second line of combined cell
                    # Format: "AMOUNT DATE\nBALANCE"
                    balance_str = None
                    if '\n' in balance_cell_str:
                        lines = [line.strip() for line in balance_cell_str.split('\n') if line.strip()]
                        if len(lines) >= 2:
                            # Balance is on second line (last line)
                            balance_str = lines[-1].strip().replace(',', '').replace('$', '')
                        elif len(lines) == 1:
                            # Only one line - check if it's a balance (number without date pattern)
                            line = lines[0]
                            if re.search(r'\d+[,.]?\d*\.?\d{0,2}', line) and not re.search(r'[A-Z]{3}\d{1,2}', line.upper()):
                                balance_str = line.replace(',', '').replace('$', '')
                    else:
                        balance_str = balance_cell_str.replace(',', '').replace('$', '')
                    
                    if balance_str and balance_str != '' and balance_str != 'nan':  # Only if not empty
                        try:
                            parsed = _parse_td_balance(balance_str)
                            if parsed is None:
                                raise ValueError("balance parse returned None")
                            balance = parsed
                            # Update closing balance - the last transaction with a balance is the closing balance
                            # But don't use BALANCE FORWARD row's balance as closing (it's the opening/continuation balance)
                            # Also don't use summary row balances
                            desc_upper = description.upper()
                            is_summary_balance = (
                                desc_upper.startswith('CREDITS') or
                                desc_upper.startswith('DEBITS') or
                                'MONTHLY AVER' in desc_upper or
                                'MONTHLY MIN' in desc_upper or
                                'DEP CONTENT' in desc_upper or
                                'NEXT STATEMENT' in desc_upper
                            )
                            if 'BALANCE FORWARD' not in desc_upper and not is_summary_balance:
                                closing_balance = balance
                        except:
                            pass
                
                transaction = {
                    'Date': date_str_formatted,
                    'Description': description,
                    'Withdrawals': withdrawal if withdrawal else 0.0,
                    'Deposits': deposit if deposit else 0.0,
                    'Balance': balance if balance else None
                }
                
                transactions.append(transaction)
            
            transactions_after_table = len(transactions)
            transactions_from_table = transactions_after_table - transactions_before_table
            if transactions_from_table > 0:
                print(f"    Added {transactions_from_table} transactions from Table {table_idx + 1} (page {table.page})")
            elif len(df_table) > start_row:
                print(f"    Warning: No transactions added from Table {table_idx + 1} (page {table.page})")
                print(f"      Started at row {start_row}, processed {rows_processed} rows, skipped {rows_skipped} rows")
                print(f"      Columns: DESC={desc_idx}, DEBIT={debit_idx}, CREDIT={credit_idx}, DATE={date_idx}, BALANCE={balance_idx}")
        
        # If stream didn't work well, try lattice
        if len(transactions) == 0:
            print("\n  Trying Lattice flavor...")
            tables_lattice = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
            print(f"  Lattice: Found {len(tables_lattice)} table(s)")
            
            # Similar parsing logic for lattice...
            # (For now, we'll focus on stream results)
    
    except Exception as e:
        print(f"  ERROR with Camelot: {e}")
        import traceback
        traceback.print_exc()
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    if len(df) == 0:
        print("  WARNING: No transactions extracted!")
        return None, None, None, None
    
    print(f"\n  Extracted {len(df)} transactions")
    
    # If closing balance not found in transactions, try to extract from PDF text
    if closing_balance is None:
        print("\n  Attempting to extract closing balance from PDF text...")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page_num in range(min(3, len(pdf.pages))):
                    page_text = pdf.pages[page_num].extract_text() or ""
                    text += page_text + "\n"
            
            # Look for closing balance patterns in text
            closing_patterns = [
                r'CLOSING\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
                r'BALANCE\s+AS\s+OF[:\s]+\$?([\d,]+\.?\d{0,2})',
                r'FINAL\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
                r'ACCOUNT\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
                r'NEW\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
            ]
            
            for pattern in closing_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        closing_balance = float(match.group(1).replace(',', ''))
                        print(f"    Found closing balance from text: ${closing_balance:,.2f}")
                        break
                    except:
                        pass
            
            # If still not found, use the last transaction's balance if available
            if closing_balance is None and len(df) > 0 and 'Balance' in df.columns:
                last_balance = df['Balance'].dropna()
                if len(last_balance) > 0:
                    closing_balance = float(last_balance.iloc[-1])
                    print(f"    Using last transaction balance: ${closing_balance:,.2f}")
            
            # Final fallback: use final running balance if available (for statements without explicit closing balance)
            if closing_balance is None and len(df) > 0 and 'Running_Balance' in df.columns:
                final_rb = float(df['Running_Balance'].iloc[-1])
                closing_balance = final_rb
                print(f"    Using final running balance as closing balance: ${closing_balance:,.2f}")
        except Exception as e:
            print(f"    Warning: Could not extract closing balance from text: {e}")
    
    # Calculate running balance
    print("\n3. CALCULATING RUNNING BALANCE:")
    print("-" * 70)
    
    if opening_balance is not None:
        print(f"  Opening Balance: ${opening_balance:,.2f}")
        # Calculate net change per transaction
        df['Net_Change'] = df['Deposits'].fillna(0) - df['Withdrawals'].fillna(0)
        # Calculate running balance: opening + cumulative net changes
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
                print("  WARNING: Could not find closing balance")
    else:
        print("  WARNING: Could not find opening balance")
    
    return df, opening_balance, closing_balance, statement_year

if __name__ == "__main__":
    # Test with first TD Bank statement
    test_file = Path("data/TD bank - 4738/1. TD 5044738 - January 31 2025.pdf")
    
    if test_file.exists():
        print("\n" + "="*70)
        print("TESTING PDFPLUMBER METHOD")
        print("="*70)
        df_pdfplumber, opening_p, closing_p, year_p = extract_td_bank_statement(str(test_file))
        
        print("\n" + "="*70)
        print("TESTING CAMELOT METHOD")
        print("="*70)
        df_camelot, opening_c, closing_c, year_c = extract_td_bank_statement_camelot(str(test_file))
        
        print("\n" + "="*70)
        print("COMPARISON")
        print("="*70)
        
        if df_pdfplumber is not None:
            print(f"\nPDFPlumber: {len(df_pdfplumber)} transactions")
            print(f"  Opening: ${opening_p:,.2f}" if opening_p else "  Opening: Not found")
            print(f"  Closing: ${closing_p:,.2f}" if closing_p else "  Closing: Not found")
            print("\n  Sample transactions:")
            print(df_pdfplumber[['Date', 'Description', 'Withdrawals', 'Deposits']].head(5).to_string())
        
        if df_camelot is not None:
            print(f"\nCamelot: {len(df_camelot)} transactions")
            print(f"  Opening: ${opening_c:,.2f}" if opening_c else "  Opening: Not found")
            print(f"  Closing: ${closing_c:,.2f}" if closing_c else "  Closing: Not found")
            print("\n  Sample transactions:")
            print(df_camelot[['Date', 'Description', 'Withdrawals', 'Deposits']].head(5).to_string())
        
        if df_pdfplumber is not None and df_camelot is not None:
            print(f"\nDifference: {abs(len(df_pdfplumber) - len(df_camelot))} transactions")
    else:
        print(f"File not found: {test_file}")

