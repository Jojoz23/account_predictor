#!/usr/bin/env python3
"""
Complete analysis script for CIBC CAD Account Statement extraction
Analyzes structure, extracts transactions, and verifies data
"""

import pdfplumber
import pandas as pd
import re
from datetime import datetime
from pathlib import Path
import sys

def _parse_cibc_transaction_line(line_text, trans_date, month_map, statement_year, all_lines, line_idx):
    """Parse a single CIBC transaction line"""
    # Pattern: "DESCRIPTION WITHDRAWAL BALANCE" or "DESCRIPTION BALANCE"
    # Sometimes: "Opening balance $3,473.20" or "Balance forward $2,369.61"
    
    # Check for opening balance or balance forward (special cases)
    if "Opening balance" in line_text or "Balance forward" in line_text:
        amount_match = re.search(r'\$?([\d,]+\.\d{2})', line_text)
        if amount_match:
            balance = float(amount_match.group(1).replace(',', ''))
            return {
                'Date': trans_date,
                'Description': line_text.replace('$', '').strip(),
                'Withdrawals': None,
                'Deposits': None,
                'Balance': balance
            }
        return None
    
    # Find all amounts in the line (numbers with decimals)
    amount_pattern = r'\b([\d,]+\.\d{2})\b'
    amount_matches = list(re.finditer(amount_pattern, line_text))
    
    if not amount_matches:
        return None
    
    # Extract amounts
    amounts = []
    for match in amount_matches:
        try:
            amount = float(match.group(1).replace(',', ''))
            amounts.append((match.start(), amount))
        except:
            pass
    
    if not amounts:
        return None
    
    # The LAST amount is always the balance
    balance = amounts[-1][1]
    
    # Description is everything before the first amount
    first_amount_pos = amounts[0][0]
    description = line_text[:first_amount_pos].strip()
    
    # Withdrawal is the first amount (if there are 2+ amounts)
    # If only 1 amount, it's the balance (opening balance case handled above)
    withdrawal = amounts[0][1] if len(amounts) >= 2 else None
    deposit = None  # CIBC format doesn't show deposits in this format (usually 0)
    
    # Read continuation lines for description (up to 3 lines)
    j = line_idx + 1
    continuation_count = 0
    while j < len(all_lines) and continuation_count < 3:
        next_line = all_lines[j].strip()
        
        # Stop if next line looks like a new transaction (has date or amounts)
        if re.match(r'^(\w{3})\s+\d{1,2}\s+', next_line):
            break
        if re.search(r'\b[\d,]+\.\d{2}\b', next_line) and len(re.findall(r'\b[\d,]+\.\d{2}\b', next_line)) >= 2:
            # Looks like a new transaction (has 2+ amounts)
            break
        if "Page" in next_line or "continued" in next_line.lower() or "Closing balance" in next_line:
            break
        
        # Add to description (could be merchant name, account number, etc.)
        if next_line:
            description += " " + next_line
            continuation_count += 1
        
        j += 1
    
    # Clean up description
    description = ' '.join(description.split()).strip()
    
    # Only create transaction if we have meaningful data
    if description or balance is not None:
        return {
            'Date': trans_date,
            'Description': description,
            'Withdrawals': withdrawal,
            'Deposits': deposit,
            'Balance': balance
        }
    
    return None

def extract_cibc_cad_statement(pdf_path):
    """Complete analysis of CIBC CAD statement"""
    print(f"\n{'='*80}")
    print(f"COMPLETE CIBC CAD ANALYSIS: {Path(pdf_path).name}")
    print(f"{'='*80}\n")
    
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    statement_start_date = None
    statement_end_date = None
    account_number = None
    
    # Extract full text
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    # Step 1: Extract statement period and year
    print("="*80)
    print("STEP 1: EXTRACTING STATEMENT PERIOD AND YEAR")
    print("="*80)
    
    # Pattern: "For Jan 1 to Jan 31, 2025"
    period_match = re.search(r'For\s+(\w+)\s+(\d{1,2})\s+to\s+(\w+)\s+(\d{1,2}),\s+(\d{4})', full_text, re.IGNORECASE)
    if period_match:
        start_month = period_match.group(1)
        start_day = period_match.group(2)
        end_month = period_match.group(3)
        end_day = period_match.group(4)
        year = int(period_match.group(5))
        
        statement_year = year
        print(f"  Found statement period: {start_month} {start_day} to {end_month} {end_day}, {year}")
        print(f"  Statement year: {statement_year}")
        
        # Parse dates
        try:
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            start_month_num = month_map.get(start_month.lower()[:3])
            end_month_num = month_map.get(end_month.lower()[:3])
            if start_month_num and end_month_num:
                statement_start_date = datetime(year, start_month_num, int(start_day))
                statement_end_date = datetime(year, end_month_num, int(end_day))
                print(f"  Parsed dates: {statement_start_date.date()} to {statement_end_date.date()}")
        except Exception as e:
            print(f"  Warning: Could not parse dates: {e}")
    else:
        print("  WARNING: Could not extract statement period")
        statement_year = 2025
        print(f"  Using fallback year: {statement_year}")
    
    # Step 2: Extract account number
    print("\n" + "="*80)
    print("STEP 2: EXTRACTING ACCOUNT INFORMATION")
    print("="*80)
    
    account_match = re.search(r'Account number\s+(\d{2}-\d+)', full_text, re.IGNORECASE)
    if account_match:
        account_number = account_match.group(1)
        print(f"  Account Number: {account_number}")
    
    branch_match = re.search(r'Branch transit number\s+(\d{5})', full_text, re.IGNORECASE)
    if branch_match:
        branch = branch_match.group(1)
        print(f"  Branch Transit: {branch}")
    
    # Step 3: Extract opening and closing balances
    print("\n" + "="*80)
    print("STEP 3: EXTRACTING OPENING AND CLOSING BALANCES")
    print("="*80)
    
    # Opening balance: "Opening balance on Jan 1, 2025 $3,473.20"
    opening_match = re.search(r'Opening balance on[^$]*\$([\d,]+\.\d{2})', full_text)
    if opening_match:
        try:
            opening_balance = float(opening_match.group(1).replace(',', ''))
            print(f"  Opening Balance: ${opening_balance:,.2f}")
        except:
            pass
    
    # Closing balance: "Closing balance on Jan 31, 2025 = $2,245.54"
    closing_match = re.search(r'Closing balance on[^$]*=\s*\$([\d,]+\.\d{2})', full_text)
    if not closing_match:
        # Alternative: "Closing balance $91,156.85"
        closing_match = re.search(r'Closing balance\s+\$([\d,]+\.\d{2})', full_text)
    if closing_match:
        try:
            closing_balance = float(closing_match.group(1).replace(',', ''))
            print(f"  Closing Balance: ${closing_balance:,.2f}")
        except:
            pass
    
    if not opening_balance:
        print("  WARNING: Could not find opening balance")
    if not closing_balance:
        print("  WARNING: Could not find closing balance")
    
    # Step 4: Analyze transaction structure
    print("\n" + "="*80)
    print("STEP 4: ANALYZING TRANSACTION STRUCTURE")
    print("="*80)
    
    # Find transaction section
    transaction_section = ""
    if "Transaction details" in full_text:
        idx = full_text.find("Transaction details")
        transaction_section = full_text[idx:]
        print("  Found 'Transaction details' section")
        
        # Show header line
        header_match = re.search(r'Date\s+Description\s+Withdrawals\s+\(\$\)\s+Deposits\s+\(\$\)\s+Balance\s+\(\$\)', transaction_section)
        if header_match:
            print("  Header format: Date | Description | Withdrawals ($) | Deposits ($) | Balance ($)")
    
    # Step 5: Extract transactions
    print("\n" + "="*80)
    print("STEP 5: EXTRACTING TRANSACTIONS")
    print("="*80)
    
    # Pattern: Date (short format like "Jan 2", "Jan 6") followed by description and amounts
    # Transaction pattern:
    # Jan 2 PURCHASE000001652010 59.17 3,414.03
    # ESSO CIRCLE K
    # 4506*********134
    # Note: Multiple transactions can occur on same date (continuation without date prefix)
    
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # Split into lines for processing
    lines = full_text.split('\n')
    
    # Find start of transaction section
    start_idx = -1
    for i, line in enumerate(lines):
        if "Transaction details" in line or (i > 0 and "Date" in lines[i-1] and "Description" in line):
            start_idx = i + 1
            break
    
    if start_idx > 0:
        print(f"  Starting transaction extraction at line {start_idx}")
        
        i = start_idx
        current_date = None
        current_month = None
        current_day = None
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and headers
            if not line or "Date" in line or ("Description" in line and "Withdrawals" in line):
                i += 1
                continue
            
            # Stop at page breaks or closing balance
            if "Page" in line or "continued on next page" in line.lower():
                i += 1
                continue
            if "Closing balance" in line and "$" in line:
                break
            
            # Check if this line starts with a date
            # Pattern: "Jan 2 DESCRIPTION ..." or "Jan 13 DESCRIPTION ..."
            date_match = re.match(r'^(\w{3})\s+(\d{1,2})\s+(.+)', line)
            if date_match:
                month_str = date_match.group(1).lower()[:3]
                day_str = date_match.group(2)
                rest = date_match.group(3).strip()
                
                if month_str in month_map:
                    current_month = month_map[month_str]
                    current_day = int(day_str)
                    year_to_use = statement_year if statement_year else 2025
                    current_date = datetime(year_to_use, current_month, current_day)
                    
                    # Process this transaction line
                    transaction = _parse_cibc_transaction_line(
                        rest, current_date, month_map, statement_year, lines, i
                    )
                    if transaction:
                        transactions.append(transaction)
            else:
                # This might be a continuation transaction on the same date
                # Check if it looks like a transaction (has amounts, no date prefix)
                # Pattern: "DESCRIPTION AMOUNT BALANCE" or "DESCRIPTION AMOUNT"
                if current_date:
                    # Check if line has numbers that look like amounts
                    amount_pattern = r'\b[\d,]+\.\d{2}\b'
                    amounts = re.findall(amount_pattern, line)
                    
                    if amounts and len(amounts) >= 1:
                        # This looks like a transaction line (has amounts)
                        # Skip if it looks like a continuation of description (just text)
                        if not re.match(r'^[A-Z\s\-]+$', line) or len(amounts) >= 2:
                            transaction = _parse_cibc_transaction_line(
                                line, current_date, month_map, statement_year, lines, i
                            )
                            if transaction:
                                transactions.append(transaction)
            
            i += 1
    
    print(f"  Extracted {len(transactions)} transactions")
    
    # Step 6: Show sample transactions
    print("\n" + "="*80)
    print("STEP 6: SAMPLE TRANSACTIONS")
    print("="*80)
    
    if transactions:
        df = pd.DataFrame(transactions)
        print(f"\n  First 5 transactions:")
        print(df.head().to_string(index=False))
        
        print(f"\n  Last 5 transactions:")
        print(df.tail().to_string(index=False))
        
        print(f"\n  Transaction counts:")
        print(f"    Total: {len(df)}")
        print(f"    With withdrawals: {df['Withdrawals'].notna().sum()}")
        print(f"    With deposits: {df['Deposits'].notna().sum()}")
        print(f"    With balance: {df['Balance'].notna().sum()}")
    else:
        print("  No transactions extracted!")
    
    # Step 7: Balance verification
    print("\n" + "="*80)
    print("STEP 7: BALANCE VERIFICATION")
    print("="*80)
    
    if transactions and opening_balance and closing_balance:
        df = pd.DataFrame(transactions)
        
        # Calculate running balance
        if 'Balance' in df.columns and df['Balance'].notna().any():
            print(f"  Using extracted balance column")
            final_balance = df['Balance'].dropna().iloc[-1] if df['Balance'].notna().any() else None
            if final_balance:
                print(f"  Final transaction balance: ${final_balance:,.2f}")
                print(f"  Closing balance from header: ${closing_balance:,.2f}")
                diff = abs(final_balance - closing_balance)
                if diff < 0.01:
                    print(f"  [OK] Balances match!")
                else:
                    print(f"  [WARNING] Balance difference: ${diff:,.2f}")
        
        # Calculate from withdrawals/deposits
        total_withdrawals = df['Withdrawals'].fillna(0).sum()
        total_deposits = df['Deposits'].fillna(0).sum()
        calculated_closing = opening_balance - total_withdrawals + total_deposits
        
        print(f"\n  Calculated closing balance: ${calculated_closing:,.2f}")
        print(f"  (Opening: ${opening_balance:,.2f} - Withdrawals: ${total_withdrawals:,.2f} + Deposits: ${total_deposits:,.2f})")
        print(f"  Actual closing balance: ${closing_balance:,.2f}")
        diff = abs(calculated_closing - closing_balance)
        if diff < 0.01:
            print(f"  [OK] Calculation matches!")
        else:
            print(f"  [WARNING] Calculation difference: ${diff:,.2f}")
    
    return {
        'transactions': transactions,
        'opening_balance': opening_balance,
        'closing_balance': closing_balance,
        'statement_year': statement_year,
        'account_number': account_number
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default to first CAD PDF
        pdf_dir = Path("data/Account Statements CAD - CIBC 4213")
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        if pdf_files:
            pdf_path = pdf_files[0]
        else:
            print("No PDF files found!")
            sys.exit(1)
    
    result = extract_cibc_cad_statement(pdf_path)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
