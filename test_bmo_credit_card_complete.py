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
        year = None
        if start_year is not None and end_year is not None and start_year != end_year:
            if start_month is not None and end_month is not None:
                if month >= start_month:
                    year = start_year
                elif month <= end_month:
                    year = end_year
                else:
                    year = end_year
        if year is None:
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
        is_credit = cleaned.upper().endswith('CR') or cleaned.upper().endswith(' CR')
        if is_credit:
            cleaned = re.sub(r'\s*CR\s*$', '', cleaned, flags=re.IGNORECASE).strip()
        if cleaned == '' or cleaned == '-':
            return None
        amount = float(cleaned)
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
        full_text = ""
        for page in pdf.pages:
            page_text = page.extract_text(layout=True)
            if not page_text:
                page_text = page.extract_text()
            full_text += page_text + "\n"
        
        period_match = re.search(r'Statement period\s+([A-Za-z]+)\.\s+(\d{1,2}),\s+(\d{4})\s+-\s+([A-Za-z]+)\.\s+(\d{1,2}),\s+(\d{4})', full_text)
        if period_match:
            statement_period_start = period_match.group(1) + '. ' + period_match.group(2) + ', ' + period_match.group(3)
            statement_period_end = period_match.group(4) + '. ' + period_match.group(5) + ', ' + period_match.group(6)
            statement_start_year = int(period_match.group(3))
            statement_end_year = int(period_match.group(6))
            statement_year = statement_end_year
            months = {
                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
            }
            statement_start_month = months.get(period_match.group(1), 1)
            statement_end_month = months.get(period_match.group(4), 12)
        
        opening_match = re.search(r'Previous total balance[^$]*\$([\d,]+\.\d{2})\s*(CR)?', full_text, re.IGNORECASE)
        if opening_match:
            opening_amt = parse_amount(opening_match.group(1))
            if opening_match.groups() and len(opening_match.groups()) > 1 and opening_match.group(2):
                opening_balance = -abs(opening_amt) if opening_amt else None
            else:
                opening_balance = opening_amt
        if opening_balance is None:
            opening_match2 = re.search(r'Previous balance[^$]*\$([\d,]+\.\d{2})\s*(CR)?', full_text, re.IGNORECASE)
            if opening_match2:
                opening_amt = parse_amount(opening_match2.group(1))
                if opening_match2.groups() and len(opening_match2.groups()) > 1 and opening_match2.group(2):
                    opening_balance = -abs(opening_amt) if opening_amt else None
                else:
                    opening_balance = opening_amt
        
        closing_match = re.search(r'Total balance\s+\$([\d,]+\.\d{2})', full_text, re.IGNORECASE)
        if closing_match:
            closing_balance = parse_amount(closing_match.group(1))
        if closing_balance is None:
            closing_match2 = re.search(r'New balance\s+\$([\d,]+\.\d{2})', full_text, re.IGNORECASE)
            if closing_match2:
                closing_balance = parse_amount(closing_match2.group(1))
        if closing_balance is None:
            closing_match3 = re.search(r'Total for card number[^$]*\$([\d,]+\.\d{2})', full_text, re.IGNORECASE)
            if closing_match3:
                closing_balance = parse_amount(closing_match3.group(1))
        
        transaction_start = re.search(r'Transactions since your last statement', full_text, re.IGNORECASE)
        if transaction_start:
            transaction_text = full_text[transaction_start.end():]
        else:
            transaction_text = full_text
        
        header_match = re.search(r'TRANS\s+DATE\s+POSTING\s+DATE\s+DESCRIPTION\s+AMOUNT', transaction_text, re.IGNORECASE)
        if header_match:
            transaction_text = transaction_text[header_match.end():]
        
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
            line_lower = line.lower()
            starts_with_date = re.match(r'^[A-Za-z]{3}\.?\s+\d{1,2}', line)
            if not starts_with_date and any(skip in line_lower for skip in skip_keywords):
                continue
            
            date_pattern = r'^([A-Za-z]{3}\.?\s+\d{1,2})\s+([A-Za-z]{3}\.?\s+\d{1,2})\s+(.+)$'
            date_match = re.match(date_pattern, line)
            if not date_match:
                date_pattern_no_space = r'^([A-Za-z]{3}\.?\s+\d{1,2})([A-Za-z]{3}\.?\s+\d{1,2})\s+(.+)$'
                date_match_no_space = re.match(date_pattern_no_space, line)
                if date_match_no_space:
                    trans_date = date_match_no_space.group(1)
                    posting_date = date_match_no_space.group(2)
                    rest = date_match_no_space.group(3)
                    line = f"{trans_date} {posting_date} {rest}"
                    date_match = re.match(date_pattern, line)
            
            amount_only_pattern = r'^([\d,]+\.\d{2})(?:\s*CR)?\s*$'
            amount_only_match = re.match(amount_only_pattern, line, re.IGNORECASE)
            amount_with_cr_pattern = r'^([\d,]+\.\d{2})\s*CR'
            amount_with_cr_match = re.match(amount_with_cr_pattern, line, re.IGNORECASE)
            amount_at_end_pattern = r'([\d,]+\.\d{2})\s*$'
            amount_at_end_match = re.search(amount_at_end_pattern, line) if pending_transaction else None
            
            if date_match:
                if pending_transaction:
                    transactions.append(pending_transaction)
                    pending_transaction = None
                trans_date_str = date_match.group(1)
                posting_date_str = date_match.group(2)
                rest = date_match.group(3).strip()
                amount_match = None
                description = None
                amount_pattern_cr = r'([\d,]+\.\d{2})\s+CR\s*$'
                amount_match = re.search(amount_pattern_cr, rest, re.IGNORECASE)
                if amount_match:
                    description = rest[:amount_match.start()].strip()
                else:
                    amount_pattern_end = r'([\d,]+\.\d{2})\s*$'
                    amount_match = re.search(amount_pattern_end, rest)
                    if amount_match:
                        description = rest[:amount_match.start()].strip()
                if amount_match:
                    amount_str = amount_match.group(1)
                    amount_pos_in_rest = rest.find(amount_str)
                    if amount_pos_in_rest >= 0:
                        text_after_amount = rest[amount_pos_in_rest + len(amount_str):].strip().upper()
                        is_credit = 'CR' in text_after_amount
                    else:
                        is_credit = False
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
                        if is_credit:
                            amount = -abs(amount)
                        description = ' '.join(description.split())
                        transactions.append({
                            'Date': parsed_date,
                            'Description': description,
                            'Amount': amount
                        })
                else:
                    amount_at_end_in_rest = re.search(r'([\d,]+\.\d{2})\s*$', rest)
                    if amount_at_end_in_rest:
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
                                continue
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
                if amount_only_match:
                    amount_str = amount_only_match.group(1)
                    amount_end_idx = line.rfind(amount_str) + len(amount_str)
                    text_after_amount = line[amount_end_idx:].strip().upper()
                    is_credit = 'CR' in text_after_amount
                else:
                    amount_str = amount_with_cr_match.group(1)
                    is_credit = True
                amount = parse_amount(amount_str)
                if amount is None and is_credit:
                    amount_str_with_cr = amount_str + ' CR'
                    amount = parse_amount(amount_str_with_cr)
                if is_credit and amount is not None:
                    amount = -abs(amount)
                if amount is not None:
                    pending_transaction['Amount'] = amount
                    pending_transaction['Description'] = ' '.join(pending_transaction['Description'].split())
                    transactions.append(pending_transaction)
                    pending_transaction = None
                else:
                    pending_transaction['Description'] += ' ' + line.strip()
            elif pending_transaction:
                amount_at_end_check = re.search(r'([\d,]+\.\d{2})\s*$', line)
                if amount_at_end_check:
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
                    pending_transaction['Description'] += ' ' + line.strip()
        
        if pending_transaction and pending_transaction.get('Amount') is not None:
            transactions.append(pending_transaction)
    
    if transactions:
        df = pd.DataFrame(transactions)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.drop(columns=['Transaction_Date', 'Posting_Date'], errors='ignore')
    else:
        df = pd.DataFrame(columns=['Date', 'Description', 'Amount'])
    
    return df, opening_balance, closing_balance, statement_year


if __name__ == '__main__':
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
