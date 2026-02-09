#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BMO Credit Card Statement Complete Extraction
Complete extraction function for BMO credit card statements
"""

import sys
import io
import pdfplumber
import pandas as pd
import re
from datetime import datetime
from pathlib import Path

# Fix encoding for Windows - only when running as main script
if __name__ == '__main__' and sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except:
        pass


def parse_bmo_cc_date(date_str, start_year=None, end_year=None, start_month=None, end_month=None, default_year=None):
    """Parse BMO credit card date format like 'Dec. 18', 'Jan. 2', etc.
    
    Determines the correct year based on statement period:
    - If statement spans years (e.g., Dec 2024 - Jan 2025), uses appropriate year
    - Otherwise uses default_year or end_year
    """
    try:
        date_str = date_str.strip()
        # Handle format like "Dec. 18" or "Dec 18"
        month_match = re.match(r'([A-Za-z]{3})\.?\s+(\d{1,2})', date_str)
        if not month_match:
            return None
        
        month_abbr = month_match.group(1)
        day = int(month_match.group(2))
        
        months = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        month = months.get(month_abbr)
        if not month:
            return None
        
        # Determine correct year
        # Priority: end_year (most common case), then default_year, then start_year, then 2025
        year = None
        
        # If statement spans across years, determine which year to use
        if start_year is not None and end_year is not None and start_year != end_year:
            if start_month is not None and end_month is not None:
                # Statement spans years (e.g., Dec 2024 - Jan 2025)
                # If date month is >= start month, likely in start year
                # If date month is <= end month, likely in end year
                # For Dec-Jan span: Dec uses start_year, Jan uses end_year
                if month >= start_month:  # Dec (12) >= Dec (12) -> use start_year
                    year = start_year
                elif month <= end_month:  # Jan (1) <= Jan (1) -> use end_year
                    year = end_year
                else:
                    # Shouldn't happen, but default to end_year
                    year = end_year
        
        # If year not determined yet, use fallback logic
        if year is None:
            # For December 2025 statements, prefer end_year (2025) over start_year
            year = end_year or default_year or start_year or 2025
        
        return datetime(year, month, day)
    except:
        return None


def parse_amount(amount_str):
    """Parse amount string like '83.25', '523.24 CR', '523.24CR', '12,029.88'
    CR suffix (with or without space) indicates a credit/refund
    """
    if not amount_str:
        return None
    try:
        cleaned = str(amount_str).replace('$', '').replace(',', '').strip()
        # Handle "CR" suffix (credit/refund) - can be attached or with space
        is_credit = cleaned.upper().endswith('CR') or cleaned.upper().endswith(' CR')
        if is_credit:
            # Remove CR (case-insensitive, with or without space)
            cleaned = re.sub(r'\s*CR\s*$', '', cleaned, flags=re.IGNORECASE).strip()
        
        if cleaned == '' or cleaned == '-':
            return None
        
        amount = float(cleaned)
        # Credits are negative (money back)
        return -amount if is_credit else amount
    except:
        return None


def extract_bmo_credit_card_statement(pdf_path):
    """Extract transactions from BMO credit card statement using pdfplumber text extraction with CR detection"""
    
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    statement_period_start = None
    statement_period_end = None
    statement_start_year = None
    statement_end_year = None
    statement_start_month = None
    statement_end_month = None
    
    with pdfplumber.open(pdf_path) as pdf:
        # Extract text from all pages for parsing
        full_text = ""
        for page in pdf.pages:
            page_text = page.extract_text(layout=True)
            if not page_text:
                page_text = page.extract_text()
            full_text += page_text + "\n"
        
        # Extract statement period and year
        period_match = re.search(r'Statement period\s+([A-Za-z]+)\.\s+(\d{1,2}),\s+(\d{4})\s+-\s+([A-Za-z]+)\.\s+(\d{1,2}),\s+(\d{4})', full_text)
        if period_match:
            statement_period_start = period_match.group(1) + '. ' + period_match.group(2) + ', ' + period_match.group(3)
            statement_period_end = period_match.group(4) + '. ' + period_match.group(5) + ', ' + period_match.group(6)
            statement_start_year = int(period_match.group(3))
            statement_end_year = int(period_match.group(6))
            statement_year = statement_end_year  # Default to end year for backward compatibility
            
            # Extract months for year determination
            months = {
                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
            }
            statement_start_month = months.get(period_match.group(1), 1)
            statement_end_month = months.get(period_match.group(4), 12)
        
        # Extract opening balance (try multiple layouts: "Previous total balance" and "Previous balance, Dec. 28, 2024")
        opening_match = re.search(r'Previous total balance[^$]*\$([\d,]+\.\d{2})\s*(CR)?', full_text, re.IGNORECASE)
        if opening_match:
            opening_amt = parse_amount(opening_match.group(1))
            if opening_match.groups() and len(opening_match.groups()) > 1 and opening_match.group(2):  # Has "CR" suffix
                opening_balance = -abs(opening_amt) if opening_amt else None
            else:
                opening_balance = opening_amt
        if opening_balance is None:
            # Fallback: "Previous balance, Dec. 28, 2024 $16,801.40" (BMO 6816 / alternate layout)
            opening_match2 = re.search(r'Previous balance[^$]*\$([\d,]+\.\d{2})\s*(CR)?', full_text, re.IGNORECASE)
            if opening_match2:
                opening_amt = parse_amount(opening_match2.group(1))
                if opening_match2.groups() and len(opening_match2.groups()) > 1 and opening_match2.group(2):
                    opening_balance = -abs(opening_amt) if opening_amt else None
                else:
                    opening_balance = opening_amt
        
        # Extract closing balance (try "Total balance" and "New balance" layouts)
        closing_match = re.search(r'Total balance\s+\$([\d,]+\.\d{2})', full_text, re.IGNORECASE)
        if closing_match:
            closing_balance = parse_amount(closing_match.group(1))
        if closing_balance is None:
            # Fallback: "New balance $16,272.66" or "New Balance            $16,272.66" (BMO 6816 layout)
            closing_match2 = re.search(r'New balance\s+\$([\d,]+\.\d{2})', full_text, re.IGNORECASE)
            if closing_match2:
                closing_balance = parse_amount(closing_match2.group(1))
        if closing_balance is None:
            # Fallback: "Total for card number XXXX XXXX XXXX 2733 $16,272.66"
            closing_match3 = re.search(r'Total for card number[^$]*\$([\d,]+\.\d{2})', full_text, re.IGNORECASE)
            if closing_match3:
                closing_balance = parse_amount(closing_match3.group(1))
        
        # Extract transaction section
        transaction_start = re.search(r'Transactions since your last statement', full_text, re.IGNORECASE)
        if transaction_start:
            transaction_text = full_text[transaction_start.end():]
        else:
            transaction_text = full_text
        
        # Find the transaction table header
        header_match = re.search(r'TRANS\s+DATE\s+POSTING\s+DATE\s+DESCRIPTION\s+AMOUNT', transaction_text, re.IGNORECASE)
        if header_match:
            transaction_text = transaction_text[header_match.end():]
        
        # Parse transactions line by line
        lines = transaction_text.split('\n')
        
        skip_keywords = [
            'continued', 'page', 'card number', 'xxxx', 'subtotal', 
            'total for card', 'transactions since', 'trans date', 
            'posting date', 'description', 'amount', 'bmo ascend',
            'mastercard', 'mr ', 'mrs ', 'ms ', 'hamza basharat'
        ]
        
        pending_transaction = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Skip summary lines and non-transaction lines
            # But don't skip if line starts with a date (it's a transaction)
            line_lower = line.lower()
            starts_with_date = re.match(r'^[A-Za-z]{3}\.?\s+\d{1,2}', line)
            
            # Only skip if line doesn't start with a date AND contains skip keywords
            if not starts_with_date and any(skip in line_lower for skip in skip_keywords):
                continue
            
            # Check if this line starts with a date pattern (e.g., "Dec. 18 Dec. 19" or "Dec. 20Dec. 22")
            # First try normal pattern with space between dates
            date_pattern = r'^([A-Za-z]{3}\.?\s+\d{1,2})\s+([A-Za-z]{3}\.?\s+\d{1,2})\s+(.+)$'
            date_match = re.match(date_pattern, line)
            
            # If no match, try pattern without space between dates: "Dec. 20Dec. 22"
            if not date_match:
                date_pattern_no_space = r'^([A-Za-z]{3}\.?\s+\d{1,2})([A-Za-z]{3}\.?\s+\d{1,2})\s+(.+)$'
                date_match_no_space = re.match(date_pattern_no_space, line)
                if date_match_no_space:
                    # Normalize: insert space between dates and re-match with standard pattern
                    trans_date = date_match_no_space.group(1)
                    posting_date = date_match_no_space.group(2)
                    rest = date_match_no_space.group(3)
                    # Reconstruct line with space between dates for consistent parsing
                    line = f"{trans_date} {posting_date} {rest}"
                    date_match = re.match(date_pattern, line)
            
            # Check if this line is just an amount (for multi-line transactions)
            # CR can be attached directly or with space: "523.24CR" or "523.24 CR"
            # Match amount at start of line, optionally followed by CR and nothing else (or just whitespace)
            amount_only_pattern = r'^([\d,]+\.\d{2})(?:\s*CR)?\s*$'
            amount_only_match = re.match(amount_only_pattern, line, re.IGNORECASE)
            
            # Also check if line starts with amount followed by CR and possibly more text
            # This handles cases like "523.24 CR" where CR might be on same line
            amount_with_cr_pattern = r'^([\d,]+\.\d{2})\s*CR'
            amount_with_cr_match = re.match(amount_with_cr_pattern, line, re.IGNORECASE)
            
            # Check if line ends with an amount (for continuation lines like "AB 39.55")
            # This handles cases where description continues on next line and amount is at end
            amount_at_end_pattern = r'([\d,]+\.\d{2})\s*$'
            amount_at_end_match = re.search(amount_at_end_pattern, line) if pending_transaction else None
            
            if date_match:
                # Save previous pending transaction if exists
                if pending_transaction:
                    transactions.append(pending_transaction)
                    pending_transaction = None
                
                trans_date_str = date_match.group(1)
                posting_date_str = date_match.group(2)
                rest = date_match.group(3).strip()
                
                # Look for amount - try end of line first, then anywhere in line with CR
                # CR can be attached directly or with space: "523.24CR" or "523.24 CR"
                amount_match = None
                description = None
                
                # First try: amount with CR (credits/payments) - check this first since they're important
                # Handle multiple spaces before CR: "      2,997.00 CR" or "4,000.00 CR"
                # Use a more flexible pattern that handles any whitespace
                amount_pattern_cr = r'([\d,]+\.\d{2})\s+CR\s*$'
                amount_match = re.search(amount_pattern_cr, rest, re.IGNORECASE)
                if amount_match:
                    # Extract everything before the amount as description
                    description = rest[:amount_match.start()].strip()
                else:
                    # Second try: amount at end of line (regular charges)
                    amount_pattern_end = r'([\d,]+\.\d{2})\s*$'
                    amount_match = re.search(amount_pattern_end, rest)
                    if amount_match:
                        # Amount at end - description is everything before it
                        description = rest[:amount_match.start()].strip()
                
                if amount_match:
                    # Amount found
                    amount_str = amount_match.group(1)
                    # Check if CR follows the amount (with or without space)
                    # Find where amount appears in original rest string
                    amount_pos_in_rest = rest.find(amount_str)
                    if amount_pos_in_rest >= 0:
                        text_after_amount = rest[amount_pos_in_rest + len(amount_str):].strip().upper()
                        is_credit = 'CR' in text_after_amount
                    else:
                        is_credit = False
                    
                    # Parse dates - pass all year info for correct year determination
                    parsed_date = parse_bmo_cc_date(
                        posting_date_str,
                        start_year=statement_start_year,
                        end_year=statement_end_year,
                        start_month=statement_start_month,
                        end_month=statement_end_month,
                        default_year=statement_year or statement_end_year or 2025
                    )
                    if not parsed_date:
                        parsed_date = parse_bmo_cc_date(
                            trans_date_str,
                            start_year=statement_start_year,
                            end_year=statement_end_year,
                            start_month=statement_start_month,
                            end_month=statement_end_month,
                            default_year=statement_year or statement_end_year or 2025
                        )
                    
                    if parsed_date:
                        amount = parse_amount(amount_str)
                        if amount is None:
                            continue
                        
                        # If detected as credit (CR suffix), make it negative
                        if is_credit:
                            amount = -abs(amount)
                        
                        description = ' '.join(description.split())
                        transactions.append({
                            'Date': parsed_date,
                            'Description': description,
                            'Amount': amount
                        })
                else:
                    # Amount is likely on next line - store as pending
                    # But first check if amount is at the end of rest (for cases like "INTEREST ADVANCES 0.04")
                    amount_at_end_in_rest = re.search(r'([\d,]+\.\d{2})\s*$', rest)
                    if amount_at_end_in_rest:
                        # Found amount at end of rest - extract it
                        amount_str = amount_at_end_in_rest.group(1)
                        description = rest[:amount_at_end_in_rest.start()].strip()
                        is_credit = 'CR' in rest.upper()
                        
                        parsed_date = parse_bmo_cc_date(
                            posting_date_str,
                            start_year=statement_start_year,
                            end_year=statement_end_year,
                            start_month=statement_start_month,
                            end_month=statement_end_month,
                            default_year=statement_year or statement_end_year or 2025
                        )
                        if not parsed_date:
                            parsed_date = parse_bmo_cc_date(
                                trans_date_str,
                                start_year=statement_start_year,
                                end_year=statement_end_year,
                                start_month=statement_start_month,
                                end_month=statement_end_month,
                                default_year=statement_year or statement_end_year or 2025
                            )
                        
                        if parsed_date:
                            amount = parse_amount(amount_str)
                            if amount is not None:
                                if is_credit:
                                    amount = -abs(amount)
                                transactions.append({
                                    'Date': parsed_date,
                                    'Description': description,
                                    'Amount': amount
                                })
                                continue  # Skip to next line
                    
                    # No amount found in rest - store as pending
                    parsed_date = parse_bmo_cc_date(
                        posting_date_str,
                        start_year=statement_start_year,
                        end_year=statement_end_year,
                        start_month=statement_start_month,
                        end_month=statement_end_month,
                        default_year=statement_year or statement_end_year or 2025
                    )
                    if not parsed_date:
                        parsed_date = parse_bmo_cc_date(
                            trans_date_str,
                            start_year=statement_start_year,
                            end_year=statement_end_year,
                            start_month=statement_start_month,
                            end_month=statement_end_month,
                            default_year=statement_year or statement_end_year or 2025
                        )
                    
                    if parsed_date:
                        description = rest.strip()
                        pending_transaction = {
                            'Date': parsed_date,
                            'Description': description,
                            'Amount': None
                        }
            
            elif (amount_only_match or amount_with_cr_match or amount_at_end_match) and pending_transaction:
                # This is the amount line for pending transaction
                if amount_only_match:
                    amount_str = amount_only_match.group(1)
                    # Check if CR follows the amount
                    amount_end_idx = line.rfind(amount_str) + len(amount_str)
                    text_after_amount = line[amount_end_idx:].strip().upper()
                    is_credit = 'CR' in text_after_amount
                else:
                    # amount_with_cr_match
                    amount_str = amount_with_cr_match.group(1)
                    is_credit = True  # CR is definitely present
                
                amount = parse_amount(amount_str)
                if amount is None:
                    # Try parsing with CR included
                    if is_credit:
                        amount_str_with_cr = amount_str + ' CR'
                        amount = parse_amount(amount_str_with_cr)
                
                if is_credit and amount is not None:
                    amount = -abs(amount)
                
                if amount is not None:
                    pending_transaction['Amount'] = amount
                    # Clean up description
                    pending_transaction['Description'] = ' '.join(pending_transaction['Description'].split())
                    transactions.append(pending_transaction)
                    pending_transaction = None
                else:
                    # Amount parsing failed, but this might be continuation text, not amount
                    # Append to description instead
                    pending_transaction['Description'] += ' ' + line.strip()
            elif pending_transaction:
                # Continuation of description - check if this line ends with an amount
                # This handles cases like "AB 88.14" where amount is at end
                amount_at_end_check = re.search(r'([\d,]+\.\d{2})\s*$', line)
                if amount_at_end_check:
                    # Found amount at end - extract it
                    amount_str = amount_at_end_check.group(1)
                    is_credit = 'CR' in line.upper()
                    text_before_amount = line[:amount_at_end_check.start()].strip()
                    if text_before_amount:
                        pending_transaction['Description'] += ' ' + text_before_amount
                    
                    amount = parse_amount(amount_str)
                    if amount is not None:
                        if is_credit:
                            amount = -abs(amount)
                        pending_transaction['Amount'] = amount
                        pending_transaction['Description'] = ' '.join(pending_transaction['Description'].split())
                        transactions.append(pending_transaction)
                        pending_transaction = None
                else:
                    # Just continuation text, no amount yet
                    pending_transaction['Description'] += ' ' + line.strip()
        
        # Add final pending transaction if exists
        if pending_transaction and pending_transaction.get('Amount') is not None:
            transactions.append(pending_transaction)
    
    # Create DataFrame
    if transactions:
        df = pd.DataFrame(transactions)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        # Drop helper columns
        df = df.drop(columns=['Transaction_Date', 'Posting_Date'], errors='ignore')
        # Opening and closing come only from the PDF (parsed above); no derivation.
    else:
        df = pd.DataFrame(columns=['Date', 'Description', 'Amount'])
    
    return df, opening_balance, closing_balance, statement_year


if __name__ == '__main__':
    # Test
    pdf_path = 'data/BMO Credit Card 2589/1. January 2025.pdf'
    df, opening, closing, year = extract_bmo_credit_card_statement(pdf_path)
    
    print(f"Statement Year: {year}")
    print(f"Opening Balance: ${opening:,.2f}" if opening else "Opening Balance: Not found")
    print(f"Closing Balance: ${closing:,.2f}" if closing else "Closing Balance: Not found")
    print(f"Transactions: {len(df)}")
    print("\nTransactions:")
    print(df.to_string())
    
    if len(df) > 0 and 'Amount' in df.columns:
        total_amount = df['Amount'].sum()
        print(f"\nTotal Amount: ${total_amount:,.2f}")
        if closing and opening:
            expected_closing = opening + total_amount
            diff = abs(expected_closing - closing)
            print(f"Expected Closing: ${expected_closing:,.2f}")
            print(f"Actual Closing: ${closing:,.2f}")
            print(f"Difference: ${diff:,.2f}")
            if diff < 0.01:
                print("✅ Balance matches!")
