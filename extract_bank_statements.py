#!/usr/bin/env python3
"""
Bank Statement PDF Extractor
Extracts transactions from Canadian bank statement PDFs (RBC, TD, BMO, Scotia, CIBC, etc.)
Supports multiple extraction strategies for different PDF formats
"""

import pdfplumber
import pandas as pd
import numpy as np
import re
from datetime import datetime
from dateutil import parser as date_parser
import warnings
import os
from pathlib import Path
import wordninja

warnings.filterwarnings('ignore')


class BankStatementExtractor:
    """
    Multi-strategy PDF extractor for Canadian bank statements
    Supports: RBC, TD, BMO, Scotiabank, CIBC, and other formats
    """
    
    def __init__(self, pdf_path):
        """
        Initialize the extractor with a PDF file
        
        Parameters:
        - pdf_path: Path to the bank statement PDF
        """
        self.pdf_path = pdf_path
        self.transactions = []
        self.metadata = {
            'bank': None,
            'account_number': None,
            'statement_period': None,
            'extraction_method': None
        }
        
    def extract(self, strategy='auto'):
        """
        Extract transactions from PDF
        
        Parameters:
        - strategy: 'auto' (try all), 'table' (pdfplumber tables), 'text' (regex parsing), 'tabula'
        
        Returns:
        - DataFrame with columns: Date, Description, Withdrawals, Deposits, Balance
        """
        print(f"🔍 Extracting transactions from: {os.path.basename(self.pdf_path)}")
        print("="*70)
        
        if strategy == 'auto':
            # Try strategies in order of reliability
            strategies = ['camelot', 'table', 'text', 'smart_table']
            results = []
            
            for strat in strategies:
                try:
                    df = self._extract_with_strategy(strat)
                    if df is not None and len(df) > 0:
                        results.append((strat, df))
                        print(f"  '{strat}' strategy: {len(df)} transactions")
                except Exception as e:
                    print(f"⚠️  Strategy '{strat}' failed: {str(e)[:100]}")
                    continue
            
            if not results:
                print("❌ All extraction strategies failed")
                return None
            
            # Use the strategy that found the most transactions
            best_strategy, best_df = max(results, key=lambda x: len(x[1]))
            print(f"✅ Using '{best_strategy}' strategy with {len(best_df)} transactions")
            self.metadata['extraction_method'] = best_strategy
            return self._clean_and_validate(best_df)
        else:
            df = self._extract_with_strategy(strategy)
            if df is not None:
                self.metadata['extraction_method'] = strategy
                return self._clean_and_validate(df)
            return None
    
    def _extract_with_strategy(self, strategy):
        """Execute a specific extraction strategy"""
        if strategy == 'camelot':
            return self._extract_camelot_tables()
        elif strategy == 'table':
            return self._extract_tables()
        elif strategy == 'text':
            return self._extract_text()
        elif strategy == 'smart_table':
            return self._extract_smart_table()
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
    
    def _extract_tables(self):
        """
        Strategy 1: Extract using pdfplumber table detection
        Works well for: TD, BMO, some RBC formats, Scotiabank (multi-line descriptions)
        """
        print("📋 Trying table extraction strategy...")
        
        all_transactions = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract tables from page
                tables = page.extract_tables()
                
                if not tables:
                    continue
                
                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 1:
                        continue
                    
                    # Check if this is a single-row transaction table (Scotiabank format)
                    # Each transaction might be in its own table
                    if len(table) == 1:
                        # Single row - likely Scotiabank format: Date | Description | Amount | Amount | Balance
                        row = table[0]
                        if len(row) >= 4:  # Need at least Date, Description, Amount, Balance
                            # Clean multi-line descriptions
                            cleaned_row = [str(cell).replace('\n', ' ').replace('  ', ' ').strip() if cell else '' for cell in row]
                            all_transactions.append(cleaned_row)
                    else:
                        # Multi-row table - traditional format
                        # Convert table to DataFrame
                        df = pd.DataFrame(table[1:], columns=table[0])
                        
                        # Try to identify transaction table by column names
                        if self._is_transaction_table(df):
                            print(f"  Found transaction table on page {page_num}, table {table_idx + 1}")
                            all_transactions.append(df)
        
        if all_transactions:
            # Check if we have single-row transactions (Scotiabank format)
            if all(isinstance(t, list) for t in all_transactions):
                # All are single rows - create DataFrame from rows
                # Assume columns: Date, Description, Withdrawals, Deposits, Balance
                df = pd.DataFrame(all_transactions, columns=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'])
                return self._standardize_columns(df)
            elif all(isinstance(t, pd.DataFrame) for t in all_transactions):
                # All are DataFrames - combine them
                combined_df = pd.concat(all_transactions, ignore_index=True)
                return self._standardize_columns(combined_df)
            else:
                # Mixed - try to combine
                dfs = []
                for t in all_transactions:
                    if isinstance(t, list):
                        dfs.append(pd.DataFrame([t], columns=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance']))
                    else:
                        dfs.append(t)
                combined_df = pd.concat(dfs, ignore_index=True)
                return self._standardize_columns(combined_df)
        
        return None
    
    def _extract_text(self):
        """
        Strategy 2: Extract using regex patterns on text
        Works well for: RBC, Scotiabank, text-based PDFs
        """
        print("📝 Trying text extraction strategy...")
        
        all_text = ""
        
        # Detect bank first to determine which PDF library to use
        # Do a quick detection pass with pdfplumber
        with pdfplumber.open(self.pdf_path) as pdf:
            sample_text = pdf.pages[0].extract_text() if pdf.pages else ""
        
        self._detect_bank(sample_text)
        
        # Use PyPDF2 for RBC (better formatting), pdfplumber for others
        if self.metadata['bank'] == 'RBC':
            try:
                # Try PyPDF2 first (better for RBC statements)
                import PyPDF2
                with open(self.pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            all_text += page_text + "\n"
            except Exception as e:
                # Fallback to pdfplumber
                print(f"PyPDF2 failed, trying pdfplumber: {str(e)}")
                with pdfplumber.open(self.pdf_path) as pdf:
                    for page in pdf.pages:
                        all_text += page.extract_text() + "\n"
        else:
            # Use pdfplumber for non-RBC banks
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    all_text += page.extract_text() + "\n"
        
        # Extract transactions using regex patterns based on bank type
        if self.metadata['bank'] == 'RBC':
            transactions = self._parse_rbc_transactions_from_text(all_text)
        else:
            transactions = self._parse_transactions_from_text(all_text)
        
        if transactions:
            df = pd.DataFrame(transactions)
            return df
        
        return None
    
    def _extract_smart_table(self):
        """
        Strategy 3: Smart table extraction with custom settings
        Works well for: Complex layouts, multi-column formats, Scotiabank single-row tables
        """
        print("🧠 Trying smart table extraction strategy...")
        
        all_transactions = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Custom table settings optimized for Scotiabank format
                table_settings = {
                    "vertical_strategy": "text",  # Use text positions instead of lines
                    "horizontal_strategy": "text",
                    "snap_tolerance": 5,
                    "join_tolerance": 5,
                    "edge_min_length": 1,
                    "min_words_vertical": 1,  # Relaxed to catch more rows
                    "min_words_horizontal": 1,
                }
                
                # Try with text-based detection (more lenient)
                tables = page.extract_tables(table_settings)
                
                # Process tables
                for table in tables:
                    if not table or len(table) < 1:
                        continue
                    
                    # Handle single-row tables (Scotiabank format)
                    if len(table) == 1:
                        row = table[0]
                        if len(row) >= 4:
                            # Clean multi-line descriptions
                            cleaned_row = [str(cell).replace('\n', ' ').replace('  ', ' ').strip() if cell else '' for cell in row]
                            all_transactions.append(cleaned_row)
                    else:
                        # Multi-row table
                        df = pd.DataFrame(table[1:], columns=table[0])
                        if self._is_transaction_table(df):
                            all_transactions.append(df)
        
        if all_transactions:
            # Check if we have single-row transactions
            if all(isinstance(t, list) for t in all_transactions):
                df = pd.DataFrame(all_transactions, columns=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'])
                return self._standardize_columns(df)
            elif all(isinstance(t, pd.DataFrame) for t in all_transactions):
                combined_df = pd.concat(all_transactions, ignore_index=True)
                return self._standardize_columns(combined_df)
            else:
                # Mixed
                dfs = []
                for t in all_transactions:
                    if isinstance(t, list):
                        dfs.append(pd.DataFrame([t], columns=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance']))
                    else:
                        dfs.append(t)
                combined_df = pd.concat(dfs, ignore_index=True)
                return self._standardize_columns(combined_df)
        
        return None
    
    def _is_transaction_table(self, df):
        """
        Check if a DataFrame is likely a transaction table
        """
        if df.empty or len(df.columns) < 3:
            return False
        
        # Convert columns to string and lowercase for comparison
        col_str = ' '.join([str(c).lower() if c else '' for c in df.columns])
        
        # Keywords that indicate transaction table
        transaction_keywords = [
            'date', 'description', 'amount', 'withdrawal', 'deposit', 
            'balance', 'debit', 'credit', 'transaction', 'details'
        ]
        
        # Count how many keywords are in columns
        keyword_count = sum(1 for keyword in transaction_keywords if keyword in col_str)
        
        # If at least 2 transaction keywords found, likely a transaction table
        return keyword_count >= 2
    
    def _detect_bank(self, text):
        """Detect bank from PDF text and extract statement year"""
        text_lower = text.lower()
        
        # IMPORTANT: Check CIBC before RBC since 'cibc' contains 'rbc'
        if 'cibc' in text_lower or 'canadian imperial' in text_lower:
            self.metadata['bank'] = 'CIBC'
        elif 'royal bank' in text_lower or 'rbc' in text_lower:
            self.metadata['bank'] = 'RBC'
        elif 'td bank' in text_lower or 'toronto-dominion' in text_lower:
            self.metadata['bank'] = 'TD'
        elif 'bank of montreal' in text_lower or 'bmo' in text_lower:
            self.metadata['bank'] = 'BMO'
        elif 'scotiabank' in text_lower or 'bank of nova scotia' in text_lower:
            self.metadata['bank'] = 'Scotiabank'
        elif 'national bank' in text_lower or 'banque nationale' in text_lower:
            self.metadata['bank'] = 'National Bank'
        
        # Extract statement year from text (common formats)
        # Look for patterns like "Jan 1 to Jan 31, 2021", "For Jan 1 to Jan 31, 2021", "2021-01-01", etc.
        year_patterns = [
            r'for\s+\w+\s+\d+\s+to\s+\w+\s+\d+,\s+(\d{4})',  # "For Jan 1 to Jan 31, 2021"
            r'(\d{4})-\d{2}-\d{2}',  # "2021-01-01"
            r'to\s+\w+\s+\d+,\s+(\d{4})',  # "to Jan 31, 2021"
            r'statement period.*?(\d{4})',  # "Statement period ... 2021"
            r'as of.*?(\d{4})',  # "as of ... 2021"
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text_lower)
            if match:
                self.metadata['statement_year'] = match.group(1)
                break
        
        if self.metadata['bank']:
            print(f"🏦 Detected bank: {self.metadata['bank']}")
    
    def _parse_transactions_from_text(self, text):
        """
        Parse transactions from raw text using regex patterns
        Enhanced for Scotiabank format with multi-line descriptions
        
        Scotiabank format: DATE DESCRIPTION AMOUNT BALANCE
        Where AMOUNT can be in either Withdrawals or Deposits column (not both)
        """
        transactions = []
        
        # Split text into lines
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if this line starts with a date (MM/DD/YYYY format for Scotiabank)
            date_match = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.+)$', line)
            
            if date_match:
                date_str = date_match.group(1)
                rest_of_line = date_match.group(2).strip()
                
                # Collect description parts and identify amounts
                description_parts = []
                withdrawal = None
                deposit = None
                balance = None
                
                # Parse amounts from the first line
                # Pattern: numbers with commas, decimals, optional - suffix
                amount_pattern = r'([\d,]+(?:\.\d{1,2})?)-?'
                
                # Find all numbers in the line
                numbers = []
                for match in re.finditer(amount_pattern, rest_of_line):
                    num_str = match.group(0)
                    numbers.append((match.start(), num_str))
                
                # The LAST number is always the balance (remove it)
                if numbers:
                    balance = numbers[-1][1]
                    numbers = numbers[:-1]  # Remove balance from consideration
                
                # Find the transaction amount - use the last number before balance as amount
                if len(numbers) >= 1:
                    # Take the last number as transaction amount (before balance)
                    transaction_amount = numbers[-1][1]
                    desc = rest_of_line[:numbers[-1][0]].strip()
                else:
                    desc = rest_of_line
                    transaction_amount = None
                
                if desc:
                    description_parts.append(desc)
                
                # Check continuation lines (lines without dates)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    
                    # Stop if we hit another transaction (starts with date)
                    if re.match(r'^\d{2}/\d{2}/\d{4}', next_line):
                        break
                    
                    # Stop if we hit a summary line
                    if 'No. of Debits' in next_line or 'Total' in next_line or 'Statement Of' in next_line:
                        break
                    
                    # Skip empty lines
                    if next_line == '':
                        j += 1
                        continue
                    
                    # This is a continuation line - add to description
                    description_parts.append(next_line)
                    j += 1
                
                # Combine description parts
                full_description = ' '.join(description_parts)
                
                # Determine if withdrawal or deposit based on description keywords
                # For Scotiabank: Use description to infer transaction type
                # Note: "MISC PAYMENT", "HEALTH/DENTAL CLAIM" are actually CREDITS (deposits)
                # as seen in the PDF table structure
                if transaction_amount:
                    # Deposit indicators
                    deposit_keywords = [
                        'DEPOSIT',
                        'HEALTH/DENTAL CLAIM',
                        'MISC PAYMENT',  # These are payments RECEIVED
                        'BUSINESS PAD',
                        'ONTARIO DRUG BENEFIT',
                        'MISC CREDIT'
                    ]
                    
                    # Withdrawal indicators  
                    withdrawal_keywords = [
                        'BILL PAYMENT',
                        'CHQ',
                        'CHEQUE',
                        'EQUIPMT. LEASE',
                        'SERVICE CHARGE',
                        'MONTHLY FEE',
                        'CRED. CARD/LOC PAYMENT',
                        'TXNFEE'
                    ]
                    
                    is_deposit = any(keyword in full_description.upper() for keyword in deposit_keywords)
                    is_withdrawal = any(keyword in full_description.upper() for keyword in withdrawal_keywords)
                    
                    if is_deposit:
                        deposit = transaction_amount
                    elif is_withdrawal:
                        withdrawal = transaction_amount
                    else:
                        # Default: if we can't tell, assume it's a withdrawal (safer for expenses)
                        withdrawal = transaction_amount
                
                # Add transaction (only if we have a valid description and it's not a header/footer)
                if full_description and not any(skip in full_description.lower() for skip in ['balance forward', 'page total']):
                    transactions.append({
                        'Date': date_str,
                        'Description': full_description,
                        'Withdrawals': withdrawal,
                        'Deposits': deposit
                    })
                
                # Move to next transaction
                i = j
            else:
                i += 1
        
        return transactions
    
    def _parse_rbc_transactions_from_text(self, text):
        """
        Parse RBC bank statement transactions from properly formatted text (PyPDF2)
        
        RBC format: 
        - Text is properly formatted with line breaks
        - Date Description Debit Credit Balance
        - Dates are only shown once per day
        - Page numbers like "1 of 5" need to be filtered out
        """
        transactions = []
        lines = text.split('\n')
        
        # Look for the transaction section
        in_transaction_section = False
        current_date = None
        
        for line in lines:
            line = line.strip()
            
            # Start parsing when we find "Account Activity Details"
            if 'Account Activity Details' in line:
                in_transaction_section = True
                continue
            
            # Stop parsing when we hit certain keywords
            if in_transaction_section and any(stop_word in line.lower() for stop_word in [
                'account fees', 'serial', 'closing balance'
            ]):
                break
            
            # Skip empty lines, headers, and page numbers
            if not line or 'Date Description' in line or 'Opening balance' in line:
                continue
            
            # Skip page numbers like "1 of 5", "2 of 5", etc.
            if re.match(r'^\d+\s+of\s+\d+$', line):
                continue
            
            # Skip non-transaction lines
            if any(skip in line.lower() for skip in [
                'business account statement', 'account number', 'how to reach us',
                'royal bank of canada', 'total deposits', 'total cheques', 'closing balance'
            ]):
                continue
            
            # Parse transaction lines
            # RBC format: "11 Dec LOAN PAYMENT 2,000.00 245.89" or "LOAN PAYMENT 2,000.00 245.89" (no date)
            
            # Check if this line starts with a date pattern: "11 Dec", "22 Dec", etc.
            date_match = re.match(r'^(\d{1,2})\s+([A-Za-z]{3})\s+(.+)$', line)
            
            if date_match:
                # This line has a date - extract it and use it for subsequent transactions
                day = date_match.group(1)
                month_abbr = date_match.group(2)
                rest_of_line = date_match.group(3).strip()
                
                # Convert month abbreviation to number
                month_map = {
                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                }
                
                month_num = month_map.get(month_abbr, '01')
                
                # Determine year (assume 2020/2021 based on the statement period)
                if month_abbr in ['Dec']:
                    year = '2020'
                else:
                    year = '2021'
                
                current_date = f"{year}-{month_num}-{day.zfill(2)}"
                
                # Parse this transaction
                transaction = self._parse_rbc_transaction_line(rest_of_line, current_date)
                if transaction:
                    transactions.append(transaction)
                    
            else:
                # This line doesn't have a date - use the current date
                if current_date and line and not any(skip in line.lower() for skip in [
                    'account fees', 'serial', 'page', 'business account', 'opening balance'
                ]):
                    transaction = self._parse_rbc_transaction_line(line, current_date)
                    if transaction:
                        transactions.append(transaction)
        
        return transactions
    
    def _parse_rbc_transaction_line(self, line, date_str):
        """
        Parse a single RBC transaction line (without date)
        
        RBC format: "DESCRIPTION AMOUNT BALANCE"
        Where AMOUNT is either in Cheques & Debits column OR Deposits & Credits column
        """
        # Clean the line
        line = line.strip()
        
        # Skip lines that are clearly not transactions
        skip_patterns = [
            'december', 'january', 'account number', 'business account',
            'royal bank', 'rbc', 'page', 'of', 'closing', 'opening'
        ]
        
        if any(pattern in line.lower() for pattern in skip_patterns):
            return None
        
        # Find all monetary amounts in the line (with proper decimal places)
        amount_pattern = r'([\d,]+\.\d{2})'
        amounts = re.findall(amount_pattern, line)
        
        if not amounts:
            return None
        
        # RBC format: Description Amount Balance
        # The last amount is always the balance
        balance_amount = amounts[-1]
        transaction_amount = amounts[0] if len(amounts) > 1 else None
        
        if not transaction_amount:
            return None
        
        # Remove amounts from description
        description = line
        description = description.replace(transaction_amount, '').replace(balance_amount, '').strip()
        
        # Clean up description
        description = re.sub(r'\s+', ' ', description).strip()
        
        # Determine if this is a debit or credit based on description keywords
        desc_upper = description.upper()
        
        # Deposit keywords (credits) - these go in Deposits & Credits column
        deposit_keywords = [
            'LOAN CREDIT', 'FEDERAL PAYMENT', 'MOBILE CHEQUE DEPOSIT',
            'REVERSED CHEQUE', 'REVERSED DEBIT', 'FEDERAL PAYMENT CANADA',
            'MOBILE CHEQUE', 'CHEQUE DEPOSIT', 'MISC PAYMENT'
        ]
        
        # Withdrawal keywords (debits) - these go in Cheques & Debits column
        withdrawal_keywords = [
            'LOAN PAYMENT', 'INTERAC', 'CHEQUE', 'E-TRANSFER', 'OVERDRAFT',
            'MONTHLY FEE', 'ACTIVITY FEE', 'ELECTRONIC TRANSACTION FEE',
            'CONTACTLESS', 'ACCOUNT TRANSFER', 'LOAN INTEREST', 'ELECTRONIC TRANSACTION',
            'CHEQUE OVER LIMIT', 'E TRANSFER', 'E TRANSFER FEE'
        ]
        
        is_deposit = any(keyword in desc_upper for keyword in deposit_keywords)
        is_withdrawal = any(keyword in desc_upper for keyword in withdrawal_keywords)
        
        withdrawal = None
        deposit = None
        
        if is_deposit:
            # This amount goes in the Deposits & Credits column
            deposit = transaction_amount
        elif is_withdrawal:
            # This amount goes in the Cheques & Debits column
            withdrawal = transaction_amount
        else:
            # Default to withdrawal if unclear
            withdrawal = transaction_amount
        
        # Return transaction if we have a valid description
        if description and len(description) > 2:
            return {
                'Date': date_str,
                'Description': description,
                'Withdrawals': withdrawal,
                'Deposits': deposit
            }
        
        return None
    
    def _standardize_columns(self, df):
        """
        Standardize column names to: Date, Description, Withdrawals, Deposits, Balance
        """
        # Remove empty columns
        df = df.dropna(axis=1, how='all')
        
        # Remove completely empty rows
        df = df.dropna(axis=0, how='all')
        
        if df.empty:
            return None
        
        # Clean multi-line descriptions (embedded newlines)
        for col in df.columns:
            if col is not None:
                df[col] = df[col].apply(lambda x: str(x).replace('\n', ' ').replace('  ', ' ').strip() if pd.notna(x) else x)
        
        # Convert all columns to strings for easier comparison
        df.columns = [str(c).strip() if c is not None else '' for c in df.columns]
        
        # Create column mapping
        col_mapping = {}
        
        for col in df.columns:
            col_lower = col.lower()
            
            # Date column
            if any(keyword in col_lower for keyword in ['date', 'trans date', 'transaction date', 'posting date']):
                col_mapping[col] = 'Date'
            
            # Description column
            elif any(keyword in col_lower for keyword in ['description', 'details', 'transaction', 'particulars', 'memo']):
                col_mapping[col] = 'Description'
            
            # Withdrawal/Debit column
            elif any(keyword in col_lower for keyword in ['withdrawal', 'withdrawals', 'debit', 'debits', 'payments', 'payment']):
                col_mapping[col] = 'Withdrawals'
            
            # Deposit/Credit column
            elif any(keyword in col_lower for keyword in ['deposit', 'deposits', 'credit', 'credits', 'receipts']):
                col_mapping[col] = 'Deposits'
            
            # Balance column
            elif any(keyword in col_lower for keyword in ['balance', 'running balance', 'account balance']):
                col_mapping[col] = 'Balance'
            
            # Amount column (generic - could be withdrawal or deposit)
            elif any(keyword in col_lower for keyword in ['amount', 'amt']):
                # If we don't have Withdrawals or Deposits yet, use this
                if 'Withdrawals' not in col_mapping.values() and 'Deposits' not in col_mapping.values():
                    col_mapping[col] = 'Amount'
        
        # Rename columns
        df = df.rename(columns=col_mapping)
        
        # If we have Amount but not Withdrawals/Deposits, split it
        if 'Amount' in df.columns and 'Withdrawals' not in df.columns and 'Deposits' not in df.columns:
            df['Amount_Clean'] = df['Amount'].astype(str).str.replace('$', '').str.replace(',', '').str.strip()
            df['Withdrawals'] = df['Amount_Clean'].apply(lambda x: x if x and ('-' in str(x) or '(' in str(x)) else None)
            df['Deposits'] = df['Amount_Clean'].apply(lambda x: x if x and '-' not in str(x) and '(' not in str(x) and x != 'None' else None)
            df = df.drop(['Amount', 'Amount_Clean'], axis=1)
        
        # Keep only standard columns (exclude Balance for cleaner output)
        standard_cols = ['Date', 'Description', 'Withdrawals', 'Deposits']
        available_cols = [c for c in standard_cols if c in df.columns]
        
        if not available_cols:
            return None
        
        df = df[available_cols]
        
        # Ensure we have at least Date and Description
        if 'Date' not in df.columns or 'Description' not in df.columns:
            return None
        
        return df
    
    def _clean_and_validate(self, df):
        """
        Clean and validate extracted transactions
        """
        if df is None or df.empty:
            return None
        
        print(f"\n🧹 Cleaning and validating data...")
        original_count = len(df)
        
        # 1. Remove rows that are likely headers/footers
        df = self._remove_headers_footers(df)
        
        # 2. Clean Date column
        if 'Date' in df.columns:
            df['Date'] = df['Date'].apply(self._parse_date)
            df = df[df['Date'].notna()]
        
        # 3. Clean Description column
        if 'Description' in df.columns:
            df['Description'] = df['Description'].astype(str).str.strip()
            # Remove "balance forward" text from descriptions but keep the transaction
            df['Description'] = df['Description'].str.replace(r'\bbalance forward\b', '', case=False, regex=True)
            df['Description'] = df['Description'].str.strip()  # Clean up extra spaces
            df = df[df['Description'] != '']
            df = df[df['Description'] != 'None']
            df = df[~df['Description'].str.lower().str.contains('beginning balance|ending balance|page total|continued', na=False)]
        
        # 4. Clean amount columns
        for col in ['Withdrawals', 'Deposits', 'Balance']:
            if col in df.columns:
                df[col] = df[col].apply(self._clean_amount)
        
        # 5. Remove rows with no amounts
        if 'Withdrawals' in df.columns and 'Deposits' in df.columns:
            df = df[(df['Withdrawals'].notna()) | (df['Deposits'].notna())]
        
        # 6. Remove duplicates - BUT preserve legitimate multiple transactions with same amounts
        # For bank statements, multiple $200 deposits on same day are DIFFERENT transactions!
        # Only remove if Date, Description, Amounts, AND Balance are all identical
        duplicate_subset = ['Date', 'Description']
        if 'Withdrawals' in df.columns:
            duplicate_subset.append('Withdrawals')
        if 'Deposits' in df.columns:
            duplicate_subset.append('Deposits')
        if 'Balance' in df.columns:
            duplicate_subset.append('Balance')  # Include balance to differentiate sequential transactions
        
        before_dedup = len(df)
        df_deduped = df.drop_duplicates(subset=duplicate_subset)
        removed_by_dedup = before_dedup - len(df_deduped)
        
        # If we're removing too many transactions (>5), it's likely legitimate repeated transactions
        # In that case, don't remove ANY - better to have potential duplicates than lose real transactions
        if removed_by_dedup > 5:
            print(f"  ⚠️  Found {removed_by_dedup} potential duplicates - keeping all (likely legitimate repeated transactions)")
            # Don't deduplicate - keep original df
        else:
            # Safe to deduplicate
            df = df_deduped
            if removed_by_dedup > 0:
                print(f"  Removed {removed_by_dedup} duplicate transactions")
        
        # 7. Reset index
        df = df.reset_index(drop=True)
        
        removed_count = original_count - len(df)
        if removed_count > 0:
            print(f"  Removed {removed_count} invalid/duplicate rows")
        
        print(f"  Final transaction count: {len(df)}")
        
        return df
    
    def _remove_headers_footers(self, df):
        """Remove common header/footer rows"""
        if 'Description' not in df.columns:
            return df
        
        # Common header/footer keywords (but NOT actual transaction types like "DEPOSIT")
        exclude_keywords = [
            'beginning balance', 'ending balance', 'opening balance', 'closing balance',
            'page total', 'subtotal', 'total deposits', 'total withdrawals',
            'continued on next page', 'continued from previous',
            'daily balance', 'account summary', 'closing totals'
        ]
        
        # Column header patterns (exact matches only - these are NOT valid transactions)
        # Note: We DON'T exclude "DEPOSIT" as a transaction type!
        column_header_patterns = [
            r'^date$',
            r'^description$', 
            r'^withdrawal[s]?/debit[s]?',  # "Withdrawals/Debits" header
            r'^deposit[s]?/credit[s]?',     # "Deposits/Credits" header
            r'^balance$',
            r'^amount$',
            r'^transaction$',
            r'^details$'
        ]
        
        def is_header_or_footer(desc):
            desc_lower = str(desc).lower().strip()
            
            # Check exclude keywords
            if any(keyword in desc_lower for keyword in exclude_keywords):
                return True
            
            # Check if it's ONLY a column header word (not "DEPOSIT" as a transaction)
            # IMPORTANT: Only match exact column headers, not transaction descriptions
            for pattern in column_header_patterns:
                if re.match(pattern, desc_lower):
                    return True
            
            return False
        
        # Remove rows that match header/footer criteria
        mask = df['Description'].apply(lambda x: not is_header_or_footer(x))
        
        return df[mask]
    
    def _parse_date(self, date_str):
        """
        Parse various date formats to datetime
        """
        if pd.isna(date_str) or date_str == '' or date_str == 'None':
            return None
        
        try:
            date_str = str(date_str).strip()
            
            # Try common formats
            # Format 1: Jan 15, 2024
            if re.match(r'[A-Z][a-z]{2}\s+\d{1,2}', date_str):
                # Add current year if not present
                if not re.search(r'\d{4}', date_str):
                    date_str = f"{date_str} {datetime.now().year}"
                return date_parser.parse(date_str)
            
            # Format 2: 01/15/2024 or 2024/01/15
            elif '/' in date_str:
                return date_parser.parse(date_str)
            
            # Format 3: 2024-01-15
            elif '-' in date_str:
                return date_parser.parse(date_str)
            
            # General fallback
            else:
                return date_parser.parse(date_str)
        
        except Exception:
            return None
    
    def _clean_amount(self, amount_str):
        """
        Clean amount strings to float
        """
        if pd.isna(amount_str) or amount_str == '' or amount_str == 'None':
            return None
        
        try:
            amount_str = str(amount_str).strip()
            
            # Remove currency symbols and commas
            amount_str = amount_str.replace('$', '').replace(',', '').replace(' ', '')
            
            # Handle parentheses (negative amounts)
            if '(' in amount_str and ')' in amount_str:
                amount_str = '-' + amount_str.replace('(', '').replace(')', '')
            
            # Convert to float
            return float(amount_str)
        
        except Exception:
            return None
    
    def save_to_excel(self, output_path=None):
        """
        Save extracted transactions to Excel
        """
        if self.transactions is None or (isinstance(self.transactions, pd.DataFrame) and self.transactions.empty):
            print("❌ No transactions to save")
            return None
        
        if output_path is None:
            # Generate output filename in data folder for privacy
            pdf_name = Path(self.pdf_path).stem
            output_path = f"data/extracted_{pdf_name}.xlsx"
        
        # Save to Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            self.transactions.to_excel(writer, sheet_name='Transactions', index=False)
            
            # Add metadata sheet
            metadata_df = pd.DataFrame([self.metadata])
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
        
        print(f"✅ Saved to: {output_path}")
        return output_path
    
    def get_transactions(self):
        """Return transactions DataFrame"""
        return self.transactions
    
    def _extract_camelot_tables(self):
        """
        Strategy: Extract using Camelot + Text extraction combined
        Works excellently for: RBC, complex bank statements
        """
        print("🐪 Trying Camelot + Text extraction combined strategy...")
        
        # Detect bank first to extract year for proper date conversion
        if not self.metadata.get('bank'):
            import pdfplumber
            with pdfplumber.open(self.pdf_path) as pdf:
                sample_text = pdf.pages[0].extract_text() if pdf.pages else ""
            self._detect_bank(sample_text)
        
        camelot_transactions = []
        text_transactions = []
        
        try:
            import camelot
            
            # Step 1: Get Camelot table structure for better parsing
            tables_stream = camelot.read_pdf(self.pdf_path, pages='all', flavor='stream')
            
            if tables_stream:
                print(f"Camelot found {len(tables_stream)} tables with stream mode")
                
                # Look for transaction tables and extract structure info
                transaction_table_info = []
                for i, table in enumerate(tables_stream):
                    df = table.df
                    
                    # Check if this looks like a transaction table
                    if self._is_transaction_table(df):
                        print(f"Table {i+1} appears to be a transaction table")
                        transaction_table_info.append({
                            'table': df,
                            'page': getattr(table, 'page', 1) if hasattr(table, 'page') else 1
                        })
                
                # Step 2: Use Camelot structure to improve text extraction
                if transaction_table_info:
                    # Extract transactions using Camelot's table structure
                    all_camelot_transactions = []
                    for table_info in transaction_table_info:
                        table_transactions = self._parse_camelot_transactions(table_info['table'])
                        if isinstance(table_transactions, pd.DataFrame) and not table_transactions.empty:
                            all_camelot_transactions.extend(table_transactions.to_dict('records'))
                    
                    # Deduplicate Camelot transactions before proceeding
                    if all_camelot_transactions:
                        camelot_df = pd.DataFrame(all_camelot_transactions)
                        
                        # Always include Balance in deduplication if available
                        # This preserves transactions with same date/description/amount but different balances
                        if 'Balance' in camelot_df.columns:
                            camelot_df = camelot_df.drop_duplicates(subset=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'])
                            print(f"Camelot deduplication: Using Balance column to preserve transactions with different balances")
                        else:
                            # Fallback if no Balance column
                            camelot_df = camelot_df.drop_duplicates(subset=['Date', 'Description', 'Withdrawals', 'Deposits'])
                        
                        camelot_transactions = camelot_df.to_dict('records')
                        print(f"After Camelot deduplication: {len(camelot_transactions)} unique transactions")
                
                # Step 3: Also do text extraction for comprehensive coverage
                text_transactions = self._extract_rbc_text_transactions()
                
                # Step 4: Use Camelot results if we have them, otherwise fall back to text
                if camelot_transactions:
                    print(f"Camelot extracted {len(camelot_transactions)} transactions with perfect debit/credit separation")
                    return pd.DataFrame(camelot_transactions)
                else:
                    print("Camelot found no transactions, falling back to text extraction")
                    return text_transactions
                    
        except ImportError:
            print("Camelot not installed, falling back to text extraction only")
            return self._extract_rbc_text_transactions()
        except Exception as e:
            print(f"Camelot extraction failed: {str(e)}, falling back to text extraction")
            return self._extract_rbc_text_transactions()
        
        return None
    
    def _extract_rbc_text_transactions(self):
        """Extract RBC transactions using text extraction method"""
        try:
            # Use PyPDF2 for better text extraction
            import PyPDF2
            with open(self.pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"PyPDF2 failed, trying pdfplumber: {str(e)}")
            with pdfplumber.open(self.pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
        
        # Parse using RBC text parser
        transactions = self._parse_rbc_transactions_from_text(text)
        
        if transactions:
            return pd.DataFrame(transactions)
        
        return pd.DataFrame()  # Return empty DataFrame instead of None
    
    def _combine_camelot_and_text(self, camelot_transactions, text_transactions):
        """Combine Camelot and text extraction results, removing duplicates"""
        if not camelot_transactions and not text_transactions:
            return []
        
        if not camelot_transactions:
            if isinstance(text_transactions, pd.DataFrame):
                return text_transactions.to_dict('records')
            return text_transactions
        
        if not text_transactions:
            return camelot_transactions
        
        # Convert text transactions to list of dicts if it's a DataFrame
        if isinstance(text_transactions, pd.DataFrame):
            if text_transactions.empty:
                return camelot_transactions
            text_list = text_transactions.to_dict('records')
        elif text_transactions is None:
            return camelot_transactions
        else:
            text_list = text_transactions
        
        # Combine all transactions
        all_transactions = camelot_transactions + text_list
        
        # Remove duplicates based on Date, Description, and Amount
        unique_transactions = []
        seen = set()
        
        for transaction in all_transactions:
            # Create a key for deduplication
            date = transaction.get('Date', '')
            desc = transaction.get('Description', '')
            withdrawal = transaction.get('Withdrawals', '')
            deposit = transaction.get('Deposits', '')
            
            key = f"{date}|{desc}|{withdrawal}|{deposit}"
            
            if key not in seen:
                seen.add(key)
                unique_transactions.append(transaction)
        
        print(f"Combined {len(camelot_transactions)} Camelot + {len(text_list)} text = {len(unique_transactions)} unique transactions")
        
        return unique_transactions
    
    def _is_transaction_table(self, df):
        """Check if a DataFrame looks like a transaction table"""
        if df.empty:
            return False
        
        # Look for common transaction table indicators
        text_content = ' '.join(df.astype(str).values.flatten()).lower()
        
        transaction_indicators = [
            'account activity', 'date', 'description', 'debit', 'credit', 
            'deposit', 'withdrawal', 'balance', 'cheque', 'interac'
        ]
        
        return sum(indicator in text_content for indicator in transaction_indicators) >= 3
    
    def _parse_camelot_transactions(self, df):
        """Parse transactions from Camelot-extracted DataFrame - SIMPLIFIED APPROACH"""
        transactions = []
        current_date = None

        # Clean the DataFrame
        df = df.fillna('')
        
        # Remove empty columns to normalize the table structure
        # Some tables have extra empty columns that throw off indexing
        # Strategy: Only drop columns that are BOTH empty in header AND have no content in data rows
        cols_to_drop = []
        header_empty_cols = []
        
        # First, find header row and identify empty header columns
        for idx, row in df.iterrows():
            row_text = ' '.join([str(cell) for cell in row.tolist()]).lower()
            if 'date' in row_text and 'description' in row_text and 'debit' in row_text:
                # This is the header row
                for col_idx, cell in enumerate(row.tolist()):
                    cell_str = str(cell).strip()
                    if not cell_str:
                        header_empty_cols.append(col_idx)
                break
        
        # Now check if those columns are also empty in all data rows
        if header_empty_cols:
            for col_idx in header_empty_cols:
                col = df.columns[col_idx]
                # Check if this column is completely empty (all cells are empty)
                if df[col].str.strip().eq('').all():
                    cols_to_drop.append(col_idx)
        
        if cols_to_drop:
            # Map column indices to column names
            cols_to_drop_names = [df.columns[i] for i in cols_to_drop if i < len(df.columns)]
            df = df.drop(columns=cols_to_drop_names)

        # Temp variable to accumulate descriptions from rows without amounts
        pending_description = ''
        pending_date = ''
        
        for idx, row in df.iterrows():
            row_list = [str(cell).strip() for cell in row.tolist()]

            # Skip header rows and empty rows
            if not any(row_list):
                continue
            
            # Skip obvious header rows and footer rows but not transaction rows
            row_text = ' '.join(row_list).lower()
            if any(header in row_text for header in ['date description', 'account activity details - continued', 'account summary', 'closing balance', 'opening balance']):
                continue
            
            # Check if this row has a date
            row_date = None
            for cell in row_list:
                # Match date patterns: "04 Jan" (RBC) or "Jan 04" (BMO)
                if re.match(r'^(\d{1,2}\s+[A-Za-z]{3}|[A-Za-z]{3}\s+\d{1,2})$', cell.strip()):
                    row_date = cell
                    current_date = cell  # Update current date for subsequent rows
                    break
            
            # Also check for date in the first cell
            if not row_date and len(row_list) > 0:
                first_cell = row_list[0].strip()
                if re.match(r'^(\d{1,2}\s+[A-Za-z]{3}|[A-Za-z]{3}\s+\d{1,2})$', first_cell):
                    row_date = first_cell
                    current_date = first_cell
            
            # Use current date if no date found in this row
            effective_date = row_date or current_date or ''
            
            # Try to extract transaction from this row
            if effective_date:
                transaction = self._extract_transaction_from_row_with_date(row_list, effective_date)
                
                if transaction:
                    # This row has an amount - check if we have pending description to prepend
                    if pending_description and pending_date == effective_date:
                        # Prepend the pending description to this transaction (for RBC/Scotiabank)
                        transaction['Description'] = pending_description + ' ' + transaction['Description']
                        transaction['Description'] = ' '.join(transaction['Description'].split())  # Clean up spaces
                        pending_description = ''
                        pending_date = ''
                    
                    transactions.append(transaction)
                else:
                    # This row has no amount - it could be:
                    # 1. A description to prepend to the NEXT transaction (RBC/Scotiabank style)
                    # 2. A continuation to append to the LAST transaction (BMO/CIBC style)
                    description_text = self._extract_description_only(row_list)
                    if description_text:
                        # Check if we have a previous transaction from the same date (comparing raw date strings)
                        last_transaction_raw_date = None
                        if transactions:
                            # Get the last transaction's date and convert back to raw format for comparison
                            last_date_str = transactions[-1]['Date']
                            # Extract the converted date and compare with effective_date
                            # Since effective_date is like "Jan 5" and last_date_str is like "2021-01-05",
                            # we need to convert effective_date for comparison
                            converted_effective_date = self._convert_rbc_date(effective_date)
                            
                            # If the last transaction's date matches the current row's date, append
                            if last_date_str == converted_effective_date:
                                # BMO/CIBC style - append to last transaction
                                transactions[-1]['Description'] += ' ' + description_text
                                transactions[-1]['Description'] = ' '.join(transactions[-1]['Description'].split())
                            else:
                                # RBC/Scotiabank style - save for prepending to next transaction
                                if pending_description:
                                    pending_description += ' ' + description_text
                                else:
                                    pending_description = description_text
                                    pending_date = effective_date
                        else:
                            # No previous transaction - save for prepending to next
                            if pending_description:
                                pending_description += ' ' + description_text
                            else:
                                pending_description = description_text
                                pending_date = effective_date
        
        # Post-process to combine split transactions
        combined_transactions = self._combine_split_transactions(transactions)
        
        if combined_transactions:
            return pd.DataFrame(combined_transactions)
        
        return pd.DataFrame()
    
    def _extract_description_only(self, row):
        """Extract only the description from a row (for rows without amounts)"""
        if len(row) < 2:
            return None
        
        # Get description from column 1 (index 1)
        description = row[1] if len(row) > 1 else ''
        
        # Also check column 2 for additional description text (like "29 Drs @ 0.75")
        if len(row) > 2 and row[2]:
            # Only add if it's not a monetary amount
            if not re.match(r'^[\d,]+\.\d{2}$', row[2].replace(',', '')):
                description += ' ' + row[2]
        
        # Clean up
        description = description.replace('\n', ' ').strip()
        description = ' '.join(description.split())  # Remove extra spaces
        
        # Return if we have any description (include short ones like "5.0")
        if description and len(description) >= 1:
            return description
        
        return None
    
    def _combine_split_transactions(self, transactions):
        """Combine transactions that were split across multiple rows"""
        if not transactions:
            return transactions
            
        combined = []
        i = 0
        
        while i < len(transactions):
            current = transactions[i]
            
            # Check if this is a partial transaction (no amount)
            is_partial = (not current.get('Withdrawals') and not current.get('Deposits'))
            
            if is_partial and i + 1 < len(transactions):
                # Try to combine with next transaction(s)
                next_trans = transactions[i + 1]
                
                # Check if the next transaction is from the same date
                if current['Date'] == next_trans['Date']:
                    # Combine descriptions
                    combined_desc = current['Description'] + ' ' + next_trans['Description']
                    combined_desc = ' '.join(combined_desc.split())  # Clean up spaces
                    
                    # Create combined transaction
                    combined_trans = {
                        'Date': current['Date'],
                        'Description': combined_desc,
                        'Withdrawals': next_trans.get('Withdrawals'),
                        'Deposits': next_trans.get('Deposits')
                    }
                    
                    combined.append(combined_trans)
                    i += 2  # Skip both transactions
                else:
                    # Different dates, don't combine - just skip the partial one
                    i += 1
            else:
                combined.append(current)
                i += 1
        
        return combined
    
    def _row_has_amount(self, row_list):
        """Check if a row contains a monetary amount"""
        if len(row_list) < 3:
            return False
        
        # Check columns 2 and 3 for amounts (debit and credit columns)
        for i in [2, 3]:
            if i < len(row_list) and row_list[i] and re.match(r'^[\d,]+\.\d{2}$', row_list[i].replace(',', '')):
                return True
        
        # Also check other columns for amounts (like balance column)
        for i in range(len(row_list)):
            if i >= 4:  # Check columns beyond debit/credit
                if row_list[i] and re.match(r'^[\d,]+\.\d{2}$', row_list[i].replace(',', '')):
                    return True
        
        return False
    
    def _extract_transaction_from_row_with_date(self, row, date):
        """Extract transaction from row with explicit date"""
        if not date:
            return None
        
        # Create row with date in first position
        row_with_date = [date] + row[1:] if len(row) > 1 else [date]
        return self._extract_transaction_from_row(row_with_date)
    
    def _extract_transaction_from_row(self, row):
        """Extract transaction data from a single row using Camelot's column structure"""
        if len(row) < 4:  # Need at least Date, Description, Debit, Credit columns
            return None
        
        date = None
        description = None
        debit_amount = None
        credit_amount = None
        
        # Camelot RBC/BMO structure: [Date, Description, Debit, Credit, Balance]
        # Find date (usually first column with date pattern)
        # Supports both "04 Jan" (RBC) and "Jan 04" (BMO)
        for i, cell in enumerate(row):
            if re.match(r'^(\d{1,2}\s+[A-Za-z]{3}|[A-Za-z]{3}\s+\d{1,2})$', cell.strip()):
                date = cell
                break
        
        if not date:
            return None
        
        # Find description (usually column 1, longest text field)
        # Allow short descriptions like "PAY" (>= 2 chars, not just > 3)
        description_candidates = [cell for cell in row[1:] if len(cell) >= 2 and not re.match(r'^[\d,.-]+$', cell)]
        if description_candidates:
            description = max(description_candidates, key=len)
            # Clean up newlines and extra spaces
            description = description.replace('\n', ' ').strip()
            description = ' '.join(description.split())  # Remove extra spaces
        
        # Look for debit and credit amounts in specific columns
        # Based on Camelot output, amounts can be in columns 2, 3, 4 depending on table structure
        # Strategy: Find the first two columns that contain monetary amounts
        if len(row) >= 3:
            amount_columns = []
            
            # Scan columns 2-5 to find debit and credit columns
            # BMO/RBC formats both have: [Date, Description, Debit(col 2), Credit(col 3), Balance(col 4+)]
            # Stop after finding 2 amount columns to avoid picking up balance
            for col_idx in range(2, min(6, len(row))):
                col_value = row[col_idx] if col_idx < len(row) else ''
                if col_value and re.match(r'^[\d,]+\.\d{2}$', col_value.replace(',', '')):
                    amount_columns.append((col_idx, col_value))
                    # Stop after finding 2 amount columns to avoid picking up balance
                    if len(amount_columns) == 2:
                        break
            
            # Determine debit and credit based on which columns have amounts
            if len(amount_columns) >= 2:
                # Two amount columns found - check if they are consecutive
                # Special case: BMO Table 1 with 4 columns [Date, Desc, Amount, Balance]
                # If we have exactly 4 columns total, the second amount is the balance
                col1_idx = amount_columns[0][0]
                col2_idx = amount_columns[1][0]
                
                if len(row) == 4 and col1_idx == 2 and col2_idx == 3:
                    # BMO 4-column format - col 2 is amount, col 3 is balance (ignore it)
                    # Determine if amount is debit or credit based on description
                    if description:
                        desc_upper = description.upper()
                        credit_keywords = ['DEPOSIT', 'CREDIT', 'PAYMENT RECEIVED', 'REVERSAL', 'DIRECT DEPOSIT']
                        is_credit = any(keyword in desc_upper for keyword in credit_keywords)
                        
                        if is_credit:
                            credit_amount = amount_columns[0][1]
                        else:
                            # Default to debit
                            debit_amount = amount_columns[0][1]
                    else:
                        debit_amount = amount_columns[0][1]
                
                elif col2_idx - col1_idx == 1:
                    # Consecutive columns - check if they are debit/credit or transaction/balance
                    # If first column is 2 and second is 3, they are debit and credit
                    # If first column is 3 and second is 4, first is credit and second is balance
                    if col1_idx == 2 and col2_idx == 3:
                        # Columns 2 and 3 - debit and credit
                        debit_amount = amount_columns[0][1]
                        credit_amount = amount_columns[1][1]
                    elif col1_idx == 3 and col2_idx == 4:
                        # Columns 3 and 4 - first is credit (col 3), second is balance (col 4 - ignore)
                        credit_amount = amount_columns[0][1]
                    else:
                        # Default: first is debit, second is credit
                        debit_amount = amount_columns[0][1]
                        credit_amount = amount_columns[1][1]
                else:
                    # Not consecutive - first is the transaction amount, second is balance (ignore it)
                    # Determine if first amount is debit or credit based on column position
                    if col1_idx == 2:
                        debit_amount = amount_columns[0][1]
                    elif col1_idx == 3:
                        credit_amount = amount_columns[0][1]
                    elif col1_idx == 4:
                        credit_amount = amount_columns[0][1]
                    else:
                        debit_amount = amount_columns[0][1]
            elif len(amount_columns) == 1:
                # Only one amount found - determine if it's debit or credit
                col_idx, amount = amount_columns[0]
                
                # For BMO (4 columns), need to determine if amount is debit or credit based on description
                if len(row) == 4 and col_idx == 2:
                    # BMO format - use description keywords to classify
                    if description:
                        desc_upper = description.upper()
                        # Credits/deposits
                        credit_keywords = ['DEPOSIT', 'CREDIT', 'PAYMENT RECEIVED', 'REVERSAL']
                        # Debits/withdrawals
                        debit_keywords = ['DEBIT CARD', 'CHEQUE', 'PRE-AUTHORIZED PAYMENT', 'WITHDRAWAL', 
                                         'FEE', 'CHARGE', 'INTERAC', 'E-TRANSFER']
                        
                        is_credit = any(keyword in desc_upper for keyword in credit_keywords)
                        is_debit = any(keyword in desc_upper for keyword in debit_keywords)
                        
                        if is_credit:
                            credit_amount = amount
                        elif is_debit:
                            debit_amount = amount
                        else:
                            # Default to debit for BMO
                            debit_amount = amount
                    else:
                        debit_amount = amount
                
                # For RBC/other formats
                elif col_idx == 2:
                    # Amount in column 2 - always debit
                    debit_amount = amount
                elif col_idx == 3:
                    # Amount in column 3 - need to determine if it's debit or credit
                    # Table 3/4: [Date, Desc, Debit(2), Credit(3), Balance(4)]
                    # Table 5: [Date, Desc, Empty(2), Debit(3), Credit(4), Empty(5), Balance(6)]
                    
                    # Check if this is Table 5 structure by looking at row length
                    # Table 5 has 7 columns, Table 3/4 have 5-6 columns
                    if len(row) >= 7:
                        # Table 5 structure - column 3 is DEBIT
                        debit_amount = amount
                    else:
                        # Table 3/4 structure - column 3 is CREDIT
                        credit_amount = amount
                elif col_idx in [4, 5]:
                    # Amount in column 4 or 5 - credit
                    credit_amount = amount
                else:
                    # Default to debit
                    debit_amount = amount
            
            # If still no amounts found, look for amounts in any column
            # This handles edge cases
            if not debit_amount and not credit_amount:
                for i in range(len(row)):
                    if i >= 2 and row[i] and re.match(r'^[\d,]+\.\d{2}$', row[i].replace(',', '')):
                        # Determine if this is debit or credit based on description and context
                        if description:
                            desc_upper = description.upper()
                            # Credits (deposits) - these should be positive
                            if any(keyword in desc_upper for keyword in [
                                'FEDERAL PAYMENT', 'LOAN CREDIT', 'REVERSED CHEQUE', 'REVERSED DEBIT'
                            ]):
                                credit_amount = row[i]
                            # Debits (withdrawals/fees) - these should be negative
                            elif any(keyword in desc_upper for keyword in [
                                'FEE', 'CHEQUE OVER', 'ACTIVITY FEE', 'MONTHLY FEE', 'TRANSACTION FEE'
                            ]):
                                debit_amount = row[i]
                            else:
                                # Default to debit (withdrawal)
                                debit_amount = row[i]
                        else:
                            # Default to debit if no description
                            debit_amount = row[i]
                        break
        
        # Convert date to standard format
        if date:
            date = self._convert_rbc_date(date)
        
        # Extract balance if available (usually the last amount column)
        balance_amount = None
        if len(row) >= 4:  # Need at least Date, Description, Amount, Balance
            # Look for balance in the last column or second-to-last column
            for i in range(len(row) - 1, max(2, len(row) - 3), -1):  # Check last few columns
                if row[i] and re.match(r'^[\d,]+\.\d{2}$', row[i].replace(',', '')):
                    # This is likely the balance column
                    balance_amount = row[i]
                    break
        
        # Return transaction if we have date, description, and at least one amount
        if date and description and (debit_amount or credit_amount):
            transaction = {
                'Date': date,
                'Description': description,
                'Withdrawals': debit_amount,
                'Deposits': credit_amount
            }
            
            # Add balance if found
            if balance_amount:
                transaction['Balance'] = balance_amount
            
            return transaction
        
        return None
    
    def _convert_rbc_date(self, date_str):
        """Convert RBC/BMO/CIBC date format to standard format"""
        # RBC format: "11 Dec", "22 Dec"
        # BMO/CIBC format: "Jan 04", "Dec 11"
        
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        # Get year from metadata if available, otherwise use default
        year = self.metadata.get('statement_year', '2022')
        
        # Try RBC format: "11 Dec"
        match = re.match(r'(\d{1,2})\s+([A-Za-z]{3})', date_str)
        if match:
            day = match.group(1)
            month_abbr = match.group(2)
            month_num = month_map.get(month_abbr, '01')
            
            # For multi-year statements (e.g., Dec 2020 - Jan 2021)
            # If year from metadata is available, use it intelligently
            if self.metadata.get('statement_year'):
                # If it's December and the statement year suggests it could be the previous year
                if month_abbr == 'Dec' and int(year) > 2020:
                    # Check if this is a cross-year statement
                    year = str(int(year) - 1)
            else:
                # Fallback logic
                if month_abbr in ['Dec']:
                    year = '2020'
                else:
                    year = '2021'
            
            return f"{year}-{month_num}-{day.zfill(2)}"
        
        # Try BMO/CIBC format: "Jan 04"
        match = re.match(r'([A-Za-z]{3})\s+(\d{1,2})', date_str)
        if match:
            month_abbr = match.group(1)
            day = match.group(2)
            month_num = month_map.get(month_abbr, '01')
            
            # Use year from metadata
            return f"{year}-{month_num}-{day.zfill(2)}"
        
        return date_str


def extract_from_pdf(pdf_path, save_excel=True, output_path=None):
    """
    Convenience function to extract transactions from a PDF
    
    Parameters:
    - pdf_path: Path to PDF file
    - save_excel: Whether to save to Excel (default: True)
    - output_path: Custom output path (default: auto-generated)
    
    Returns:
    - DataFrame with transactions
    """
    extractor = BankStatementExtractor(pdf_path)
    df = extractor.extract(strategy='auto')
    
    if df is not None and len(df) > 0:
        extractor.transactions = df
        
        if save_excel:
            extractor.save_to_excel(output_path)
        
        return df
    else:
        print("❌ Failed to extract transactions")
        return None


def extract_from_folder(folder_path, save_combined=True):
    """
    Extract transactions from all PDFs in a folder
    
    Parameters:
    - folder_path: Path to folder containing PDF files
    - save_combined: Whether to save combined Excel (default: True)
    
    Returns:
    - Combined DataFrame with all transactions
    """
    folder = Path(folder_path)
    pdf_files = list(folder.glob('*.pdf'))
    
    if not pdf_files:
        print(f"❌ No PDF files found in {folder_path}")
        return None
    
    print(f"📁 Found {len(pdf_files)} PDF files")
    print("="*70)
    
    all_transactions = []
    
    for pdf_file in pdf_files:
        print(f"\n📄 Processing: {pdf_file.name}")
        try:
            df = extract_from_pdf(str(pdf_file), save_excel=True)
            if df is not None:
                df['Source_File'] = pdf_file.name
                all_transactions.append(df)
        except Exception as e:
            print(f"❌ Error processing {pdf_file.name}: {e}")
            continue
    
    if not all_transactions:
        print("\n❌ No transactions extracted from any files")
        return None
    
    # Combine all transactions
    combined_df = pd.concat(all_transactions, ignore_index=True)
    
    print("\n" + "="*70)
    print(f"✅ Total transactions extracted: {len(combined_df)}")
    print(f"📊 From {len(all_transactions)} files")
    
    if save_combined:
        output_path = folder / "all_transactions_combined.xlsx"
        combined_df.to_excel(output_path, index=False)
        print(f"💾 Saved combined file: {output_path}")
    
    return combined_df


if __name__ == '__main__':
    import sys
    
    # Command-line usage
    if len(sys.argv) < 2:
        print("="*70)
        print("BANK STATEMENT PDF EXTRACTOR")
        print("="*70)
        print("\nUsage:")
        print("  python extract_bank_statements.py <pdf_file>")
        print("  python extract_bank_statements.py <folder_path>")
        print("\nExamples:")
        print("  python extract_bank_statements.py statement_jan2024.pdf")
        print("  python extract_bank_statements.py statements/")
        print("\nSupports: RBC, TD, BMO, Scotiabank, CIBC, and other Canadian banks")
        print("="*70)
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    if os.path.isfile(input_path):
        # Single PDF file
        extract_from_pdf(input_path, save_excel=True)
    elif os.path.isdir(input_path):
        # Folder of PDFs
        extract_from_folder(input_path, save_combined=True)
    else:
        print(f"❌ Path not found: {input_path}")

