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
            'extraction_method': None,
            'statement_year': None,
            'is_credit_card': False,
            'statement_start_year': None,
            'statement_end_year': None
        }
        
        # Detect if this is a credit card statement (before year extraction)
        try:
            import pdfplumber
            with pdfplumber.open(self.pdf_path) as pdf:
                sample_text = pdf.pages[0].extract_text() if pdf.pages else ""
            if self._detect_credit_card_statement(sample_text):
                self.metadata['is_credit_card'] = True
                print(f"  💳 Detected as credit card statement")
        except:
            pass
        
        # Extract statement year early
        self.metadata['statement_year'] = self._extract_statement_year()
        
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
        
        # Detect bank first to extract year for proper date conversion
        if not self.metadata.get('bank'):
            with pdfplumber.open(self.pdf_path) as pdf_temp:
                sample_text = pdf_temp.pages[0].extract_text() if pdf_temp.pages else ""
            self._detect_bank(sample_text)
        
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
        elif 'nova scotia' in text_lower and 'bank' in text_lower:
            # More specific: "Bank of Nova Scotia" or "Nova Scotia" + "Bank"
            # Check that it's not just a mention in an address
            if 'bank of nova scotia' in text_lower or ('registered trademark' in text_lower and 'nova scotia' in text_lower):
                self.metadata['bank'] = 'Scotiabank'
        elif 'scotia' in text_lower and ('financial services agreement' in text_lower or 'business banking services agreement' in text_lower or 
                                         ('registered trademark' in text_lower and 'scotia' in text_lower)):
            # Scotiabank-specific phrases that won't match other banks
            self.metadata['bank'] = 'Scotiabank'
        elif 'national bank' in text_lower or 'banque nationale' in text_lower:
            self.metadata['bank'] = 'National Bank'
        
        # Extract statement year from text (common formats)
        # Look for patterns like "Jan 1 to Jan 31, 2021", "For Jan 1 to Jan 31, 2021", "2021-01-01", etc.
        # NOTE: For cross-year statements, we prefer the ENDING year (e.g., Dec 2017 - Jan 2018 → use 2018)
        year_patterns = [
            r'ending\s+\w+\s+\d+,\s*(\d{4})',  # "ending July 31, 2024"
            r'-\s*\w+\s*\d+/(\d{2})',  # "DEC29/17 - JAN 31/18" -> extract ending year 18
            r'to\s*\w+\s*\d+,\s*(\d{4})',  # "to January 30, 2024" or "toJanuary30,2024"
            r'\w+\s*\d+,\s*(\d{4})\s*to',  # "December 29, 2023 to" or "December29,2023to"
            r'for\s+\w+\s+\d+\s+to\s+\w+\s+\d+,\s+(\d{4})',  # "For Jan 1 to Jan 31, 2021"
            r'/(\d{2})\s*-\s*\w+\s+\d+/\d{2}',  # "OCT 31/22 - NOV 30/22" -> extract 22
            r'(\d{4})-\d{2}-\d{2}',  # "2021-01-01"
            r'statement period.*?(\d{4})',  # "Statement period ... 2021"
            r'as of.*?(\d{4})',  # "as of ... 2021"
        ]
        
        # Only extract year if not already set (to avoid overwriting correct year from _extract_statement_year)
        if not self.metadata.get('statement_year'):
            for pattern in year_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    year = match.group(1)
                    # Handle 2-digit years (22 -> 2022)
                    if len(year) == 2:
                        year = '20' + year
                    # Validate year is reasonable (2015-2035)
                    if 2015 <= int(year) <= 2035:
                        self.metadata['statement_year'] = year
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
        
        # Keep standard columns
        # For RBC, preserve Balance column as it's reliable from Camelot extraction
        # For other banks, preserve Balance if available (they might use it)
        standard_cols = ['Date', 'Description', 'Withdrawals', 'Deposits']
        
        # Preserve Balance column if it exists (especially important for RBC)
        if 'Balance' in df.columns:
            standard_cols.append('Balance')
        
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
            # Normalize spacing and tokenization issues (e.g., 'Misc PaymentAMEX' → 'Misc Payment AMEX')
            df['Description'] = df['Description'].apply(self._normalize_description_text)
            # Remove "balance forward" text from descriptions but keep the transaction
            df['Description'] = df['Description'].str.replace(r'\bbalance forward\b', '', case=False, regex=True)
            # Remove "Account Fees: $X.XX" suffix from descriptions (RBC specific)
            df['Description'] = df['Description'].str.replace(r'\s*Account Fees:\s*\$[\d,]+\.\d{2}$', '', case=False, regex=True)
            df['Description'] = df['Description'].str.strip()  # Clean up extra spaces
            df = df[df['Description'] != '']
            df = df[df['Description'] != 'None']
            df = df[~df['Description'].str.lower().str.contains('beginning balance|ending balance|page total|continued', na=False)]
        
        # 4. Clean amount columns
        is_credit_card = self.metadata.get('is_credit_card', False)
        bank = (self.metadata.get('bank') or '').upper()
        
        # For credit cards, clean Amount column; for bank accounts, clean Withdrawals/Deposits
        if is_credit_card and bank == 'SCOTIABANK':
            if 'Amount' in df.columns:
                df['Amount'] = df['Amount'].apply(self._clean_amount)
        else:
            for col in ['Withdrawals', 'Deposits', 'Balance']:
                if col in df.columns:
                    df[col] = df[col].apply(self._clean_amount)
        
        # 5. Remove rows with no amounts
        # For credit cards, require Amount column
        if is_credit_card and bank == 'SCOTIABANK':
            if 'Amount' in df.columns:
                before_amount_filter = len(df)
                df = df[df['Amount'].notna()]
                removed_by_amount_filter = before_amount_filter - len(df)
                if removed_by_amount_filter > 0:
                    print(f"  Removed {removed_by_amount_filter} rows with no Amount (credit card)")
        # For Scotiabank bank accounts, keep transactions with Balance even if amounts are missing
        # (Balance can be used to infer the transaction amount)
        elif 'Withdrawals' in df.columns and 'Deposits' in df.columns:
            before_amount_filter = len(df)
            if bank == 'SCOTIABANK' and 'Balance' in df.columns:
                # For Scotiabank, keep transactions that have either amounts OR balance
                df = df[(df['Withdrawals'].notna()) | (df['Deposits'].notna()) | (df['Balance'].notna())]
            else:
                # For other banks, require at least one amount
                df = df[(df['Withdrawals'].notna()) | (df['Deposits'].notna())]
            removed_by_amount_filter = before_amount_filter - len(df)
            if removed_by_amount_filter > 0:
                print(f"  Removed {removed_by_amount_filter} rows with no amounts (both Withdrawals and Deposits are NaN)")
        
        # 6. Remove duplicates - BUT preserve legitimate multiple transactions with same amounts
        # For bank statements, multiple $200 deposits on same day are DIFFERENT transactions!
        # For credit cards, use Amount column for deduplication
        # For RBC statements, use running balance to help with deduplication
        # Only deduplicate transactions that don't have a balance value
        if is_credit_card and bank == 'SCOTIABANK':
            # For credit cards, use Amount column for deduplication
            duplicate_subset = ['Date', 'Description', 'Amount']
            print(f"  Scotia Visa: Using Amount column for deduplication")
        elif bank == 'RBC':
            # For RBC, only deduplicate transactions without balance values
            # Use running balance to differentiate otherwise identical transactions
            duplicate_subset = ['Date', 'Description', 'Withdrawals', 'Deposits']
            # Don't include Balance - use running balance instead
        elif bank == 'SCOTIABANK':
            # For Scotiabank, ALWAYS use Balance column if available for deduplication
            duplicate_subset = ['Date', 'Description', 'Withdrawals', 'Deposits']
            if 'Balance' in df.columns:
                duplicate_subset.append('Balance')
                print(f"  Scotiabank: Using Balance column for deduplication")
        else:
            # For other banks, use standard deduplication
            duplicate_subset = ['Date', 'Description', 'Withdrawals', 'Deposits']
            if 'Balance' in df.columns:
                duplicate_subset.append('Balance')
        
        before_dedup = len(df)
        df_deduped = df.drop_duplicates(subset=duplicate_subset)
        removed_by_dedup = before_dedup - len(df_deduped)
        
        # Use standard deduplication for all banks
        if removed_by_dedup >= 5:
            # Only deduplicate if 5+ transactions would be removed
            # Store removed transactions for analysis
            removed_transactions = df[~df.index.isin(df_deduped.index)]
            df = df_deduped
            print(f"  Removed {removed_by_dedup} duplicate transactions (5+ duplicates found)")
            
            # Store removed transactions for dynamic programming analysis
            self.removed_transactions = removed_transactions
        else:
            # Keep all transactions if fewer than 5 duplicates
            print(f"  Found {removed_by_dedup} potential duplicates - keeping all (likely legitimate repeated transactions)")
            # Don't deduplicate - keep original df
            self.removed_transactions = None
        
        # 6b. Extra-conservative pass for RBC: remove only adjacent exact duplicates
        # This catches page-repeat artifacts while preserving legitimate repeated transactions
        if self.metadata.get('bank') == 'RBC' and len(df) > 1:
            df = df.reset_index(drop=True)
            adjacent_subset = ['Date', 'Description', 'Withdrawals', 'Deposits']
            common_cols = [c for c in adjacent_subset if c in df.columns]
            if len(common_cols) == 4:
                same_as_prev = (df[common_cols] == df[common_cols].shift(1)).all(axis=1)
                # Never remove known legitimate repeats like BR TO BR transfers
                protect_legit = df['Description'].str.contains(r'BR TO BR', case=False, na=False)
                to_drop = same_as_prev & (~protect_legit)
                removed_adjacent = int(to_drop.sum())
                if removed_adjacent > 0:
                    print(f"  Removed {removed_adjacent} adjacent duplicate transactions (RBC page-repeat)")
                    df = df[~to_drop]

        # 7. Reset index
        df = df.reset_index(drop=True)
        
        # 8. Add running balance verification for all banks (was RBC-only)
        df = self._verify_running_balance(df)
        
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

    def _normalize_description_text(self, text):
        """Normalize description spacing and common tokenization issues.
        - Trim
        - Replace newlines with a single space
        - Collapse multiple spaces to single
        - Ensure a space after 'Misc Payment' if missing
        """
        s = str(text or '')
        # Remove surrounding quotes that may come from CSV/Excel exports
        if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
            s = s[1:-1]
        # Normalize newlines → single space
        s = re.sub(r"[\r\n]+", " ", s)
        s = s.strip()
        # Ensure a space after 'Misc Payment' even if Camelot concatenated the next token
        s = re.sub(r'(?i)\bmisc\s+payment(?=\S)', 'Misc Payment ', s)
        s = re.sub(r'(?i)\bmisc\s*payment\s*(?=\S)', 'Misc Payment ', s)
        # Collapse any repeated whitespace
        s = re.sub(r'\s+', ' ', s)
        return s.strip()
    
    def _smart_deduplicate_rbc(self, df, duplicate_subset):
        """Smart deduplication for RBC statements using running balance"""
        if len(df) == 0:
            return df
        
        # First, calculate running balance to help identify duplicates
        df = self._verify_running_balance(df)
        
        # Create a hash for each row to identify duplicates
        df['_hash'] = df[duplicate_subset].apply(lambda x: hash(tuple(x)), axis=1)
        
        # For RBC statements, only remove duplicates if they have the same running balance
        # This ensures we don't remove legitimate transactions that happen to have same details
        df['_keep'] = True
        
        # Find groups of transactions with same hash
        for hash_value in df['_hash'].unique():
            same_hash = df[df['_hash'] == hash_value]
            
            # Default: keep all transactions
            df.loc[same_hash.index, '_keep'] = True
            
            if len(same_hash) >= 2:
                running_balances = same_hash['Running_Balance'].unique()
                
                # Remove duplicates if we got 2+ identical rows with same running balance
                # This catches real duplicates while preserving legitimate transactions
                if len(running_balances) == 1:
                    # All have same running balance - these are likely true duplicates
                    # Keep only the first one
                    df.loc[same_hash.index, '_keep'] = False
                    df.loc[same_hash.index[0], '_keep'] = True
        
        # Filter to keep only selected rows
        df_filtered = df[df['_keep']].drop(columns=['_hash', '_keep'])
        
        removed_count = len(df) - len(df_filtered)
        if removed_count > 0:
            print(f"  Removed {removed_count} duplicate transactions (same details and running balance)")
        else:
            print(f"  No duplicates found - keeping all {len(df)} transactions")
        
        return df_filtered.reset_index(drop=True)
    
    def _verify_running_balance(self, df):
        """Calculate running balance using actual balance values when available"""
        if len(df) == 0:
            return df
        
        print("  🔍 Calculating running balance...")
        
        # Extract opening and closing balances from the PDF
        opening_balance, closing_balance = self._extract_opening_closing_balances()
        
        bank = (self.metadata.get('bank') or '').upper()
        is_credit_card = self.metadata.get('is_credit_card', False)
        
        # SCOTIA VISA: Calculate running balance from opening + Amount column
        if is_credit_card and bank == 'SCOTIABANK':
            if opening_balance is not None:
                print(f"    📊 Scotia Visa: Using opening balance: ${opening_balance:,.2f}")
                if 'Amount' in df.columns:
                    df['Running_Balance'] = opening_balance + df['Amount'].cumsum()
                    
                    # Verify against closing balance
                    if closing_balance is not None:
                        final_running = df['Running_Balance'].iloc[-1]
                        difference = abs(final_running - closing_balance)
                        if difference < 0.01:
                            print(f"    ✅ Scotia Visa: Running balance matches closing balance (${final_running:,.2f})")
                        else:
                            print(f"    ⚠️  Scotia Visa: Running balance mismatch - Calculated: ${final_running:,.2f}, Statement: ${closing_balance:,.2f}, Difference: ${difference:,.2f}")
                else:
                    print(f"    ⚠️  Scotia Visa: No Amount column found, cannot calculate running balance")
            else:
                print(f"    ⚠️  Scotia Visa: No opening balance found, cannot calculate running balance")
            
            # Store balances in metadata
            if opening_balance is not None:
                self.metadata['opening_balance'] = opening_balance
            if closing_balance is not None:
                self.metadata['closing_balance'] = closing_balance
            
            return df
        
        # CIBC-specific: prefer deriving opening/closing from the statement Balance column table
        # even if regex found values, as regex may pick summary artifacts
        if bank == 'CIBC':
            if 'Balance' in df.columns and df['Balance'].notna().any():
                first_idx = df['Balance'].first_valid_index()
                last_idx = df['Balance'].last_valid_index()
                if first_idx is not None and last_idx is not None:
                    first_row = df.loc[first_idx]
                    first_w = float(first_row.get('Withdrawals', 0)) if pd.notna(first_row.get('Withdrawals')) else 0
                    first_d = float(first_row.get('Deposits', 0)) if pd.notna(first_row.get('Deposits')) else 0
                    first_net = first_d - first_w
                    inferred_open = float(first_row['Balance']) - first_net
                    opening_balance = inferred_open
                    closing_balance = float(df.loc[last_idx]['Balance'])
        
        # SCOTIABANK: Use opening balance from BALANCE FORWARD if available
        if bank == 'SCOTIABANK' and self.metadata.get('scotiabank_opening_balance_from_bf') is not None:
            opening_balance = self.metadata.get('scotiabank_opening_balance_from_bf')
            print(f"    📊 Scotiabank: Using opening balance from BALANCE FORWARD: ${opening_balance:,.2f}")
        
        # Fallbacks by using Balance column if present (for all banks including RBC)
        if opening_balance is None or closing_balance is None:
            if 'Balance' in df.columns and df['Balance'].notna().any():
                first_idx = df['Balance'].first_valid_index()
                last_idx = df['Balance'].last_valid_index()
                if first_idx is not None and last_idx is not None:
                    # Infer opening as balance before first transaction
                    first_row = df.loc[first_idx]
                    first_w = float(first_row.get('Withdrawals', 0)) if pd.notna(first_row.get('Withdrawals')) else 0
                    first_d = float(first_row.get('Deposits', 0)) if pd.notna(first_row.get('Deposits')) else 0
                    first_net = first_d - first_w
                    inferred_open = float(first_row['Balance']) - first_net
                    # For Scotiabank, prefer BALANCE FORWARD over inferred
                    if bank != 'SCOTIABANK' or opening_balance is None:
                        opening_balance = inferred_open if opening_balance is None else opening_balance
                    # For Scotiabank, extract closing balance from last transaction's Balance column
                    if bank == 'SCOTIABANK' and closing_balance is None:
                        last_balance = df.loc[last_idx]['Balance']
                        if pd.notna(last_balance):
                            closing_balance = float(last_balance)
                            print(f"    📊 Scotiabank: Extracted closing balance from last transaction: ${closing_balance:,.2f}")
                    else:
                        closing_balance = float(df.loc[last_idx]['Balance']) if closing_balance is None else closing_balance
            
        if opening_balance is None or closing_balance is None:
            print("    ⚠️  Could not extract opening/closing balances from PDF")
            return df
        
        print(f"    📊 Opening balance: ${opening_balance:,.2f}")
        print(f"    📊 Closing balance: ${closing_balance:,.2f}")
        
        # Initialize running balance column
        df['Running_Balance'] = 0.0
        running_balance = opening_balance
        
        # Check if we have actual balance values from the statement
        # CIBC and BMO: Ignore Balance column, calculate from opening + flows
        # SCOTIABANK: Calculate from flows (ignore Balance column for running balance calculation)
        # Other banks: Use Balance column if available, otherwise calculate
        has_balance_column = 'Balance' in df.columns
        if bank == 'CIBC' or bank == 'BMO' or bank == 'SCOTIABANK':
            # CIBC, BMO, and Scotiabank: ignore the per-row Balance column for running steps; compute from opening + flows
            # This ensures consistency and avoids using potentially incorrect balance values
            has_balance_column = False
        
        print(f"    📊 Has Balance column: {has_balance_column}")
        if has_balance_column:
            non_null_balance_count = df['Balance'].notna().sum()
            print(f"    📊 Non-null Balance values: {non_null_balance_count}")
        
        for idx, row in df.iterrows():
            # Check if this transaction has an actual balance value from the statement
            if has_balance_column and pd.notna(row.get('Balance')):
                # Use the actual balance from the statement
                actual_balance = float(row.get('Balance'))
                df.at[idx, 'Running_Balance'] = actual_balance
                running_balance = actual_balance  # Update running balance to match actual
                print(f"    📊 Using actual balance: ${actual_balance:,.2f} for transaction {idx}")
            else:
                # Calculate running balance for transactions without balance values
                withdrawals = float(row.get('Withdrawals', 0)) if pd.notna(row.get('Withdrawals')) else 0
                deposits = float(row.get('Deposits', 0)) if pd.notna(row.get('Deposits')) else 0
                net_change = deposits - withdrawals
                
                running_balance += net_change
                df.at[idx, 'Running_Balance'] = running_balance
        
        # Verify final balance matches closing balance
        final_calculated_balance = running_balance
        balance_diff = abs(final_calculated_balance - closing_balance)
        
        print(f"    📊 Calculated final balance: ${final_calculated_balance:,.2f}")
        
        if balance_diff < 0.01:  # Within 1 cent
            print("    ✅ Running balance matches closing balance!")
        else:
            print(f"    ⚠️  Balance mismatch: ${balance_diff:,.2f} difference")
            print("    💡 This may indicate missing or incorrect transactions")
            
            # Use dynamic programming to analyze the mismatch
            df = self._find_missing_transactions_dp(df, opening_balance, closing_balance)
        
        return df
    
    def _find_missing_transactions_dp(self, df, opening_balance, closing_balance):
        """Use dynamic programming to find missing transactions"""
        if len(df) == 0:
            return df
        
        print("  🔍 Using dynamic programming to find missing transactions...")
        
        # Calculate expected balance for each transaction
        df['Expected_Balance'] = 0.0
        running_balance = opening_balance
        
        for idx, row in df.iterrows():
            withdrawals = float(row.get('Withdrawals', 0)) if pd.notna(row.get('Withdrawals')) else 0
            deposits = float(row.get('Deposits', 0)) if pd.notna(row.get('Deposits')) else 0
            net_change = deposits - withdrawals
            
            running_balance += net_change
            df.at[idx, 'Expected_Balance'] = running_balance
        
        # Find transactions where expected balance doesn't match actual balance
        # (if we had actual balance values)
        balance_mismatches = []
        
        # For now, let's identify potential missing transactions by looking for
        # large jumps in the expected balance that might indicate missing transactions
        df['Balance_Jump'] = df['Expected_Balance'].diff().abs()
        
        # Find transactions with unusually large balance jumps
        large_jumps = df[df['Balance_Jump'] > 1000]  # Adjust threshold as needed
        
        if len(large_jumps) > 0:
            print(f"    📊 Found {len(large_jumps)} transactions with large balance jumps:")
            # Show only first 5 for performance
            for idx, row in large_jumps.head(5).iterrows():
                jump_amount = row['Balance_Jump']
                print(f"      Transaction {idx}: {row['Description']} - Jump: ${jump_amount:,.2f}")
            if len(large_jumps) > 5:
                print(f"      ... and {len(large_jumps) - 5} more")
        
        # Calculate the final balance mismatch
        final_expected = df['Expected_Balance'].iloc[-1]
        
        raw_diff = closing_balance - final_expected  # positive => we're short money, probably dropped a deposit
        abs_diff = abs(raw_diff)
        
        print(f"    📊 Final expected balance: ${final_expected:,.2f}")
        print(f"    📊 Actual closing balance: ${closing_balance:,.2f}")
        print(f"    📊 Balance difference: ${abs_diff:,.2f} (raw diff: {raw_diff:+.2f})")
        
        if abs_diff > 0.01:
            print(f"    💡 Potential missing transactions worth: ${abs_diff:,.2f}")
            
            # Use dynamic programming to analyze removed transactions
            if hasattr(self, 'removed_transactions') and self.removed_transactions is not None:
                transactions_to_add_back = self._analyze_removed_transactions_dp(
                    self.removed_transactions,
                    abs_diff,
                    raw_diff
                )
                
                # Add back the incorrectly removed transactions
                if transactions_to_add_back:
                    df = self._add_back_transactions(df, transactions_to_add_back, abs_diff)
            else:
                # Fallback to analyzing current transactions
                self._find_transaction_combinations(df, abs_diff)
        
        return df
    
    def _add_back_transactions(self, df, transactions_to_add_back, balance_diff):
        """Add back incorrectly removed transactions"""
        print(f"    🔄 Adding back {len(transactions_to_add_back)} incorrectly removed transactions...")
        
        # Create new rows for the transactions to add back
        new_rows = []
        for amount_type, original_idx, amount, description in transactions_to_add_back:
            # Get the original transaction from removed_transactions
            original_transaction = self.removed_transactions.loc[original_idx]
            
            # Create a new row with the same structure as df
            new_row = {
                'Date': original_transaction['Date'],
                'Description': original_transaction['Description'],
                'Withdrawals': original_transaction['Withdrawals'],
                'Deposits': original_transaction['Deposits']
            }
            
            # Add any other columns that exist in df
            for col in df.columns:
                if col not in new_row:
                    if col in original_transaction:
                        new_row[col] = original_transaction[col]
                    else:
                        new_row[col] = None
            
            new_rows.append(new_row)
            print(f"      ✅ Adding back: {description} - ${amount:,.2f} ({amount_type})")
        
        # Convert to DataFrame and insert at correct chronological position
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            
            # Insert transactions at their correct chronological position
            df = self._insert_transactions_at_correct_position(df, new_df)
            
            print(f"    ✅ Successfully added back {len(new_rows)} transactions at correct positions")
            print(f"    📊 New transaction count: {len(df)}")
        
        return df
    
    def _insert_transactions_at_correct_position(self, df, new_df):
        """Insert restored transactions at their correct chronological position"""
        if len(new_df) == 0:
            return df
        
        # Combine all transactions
        all_transactions = pd.concat([df, new_df], ignore_index=True)
        
        # Sort by date to ensure correct chronological order
        all_transactions = all_transactions.sort_values('Date').reset_index(drop=True)
        
        # Recalculate running balance with correct order
        all_transactions = self._recalculate_running_balance(all_transactions)
        
        return all_transactions
    
    def _recalculate_running_balance(self, df):
        """Recalculate running balance after adding back transactions"""
        if len(df) == 0:
            return df
        
        # Sort by date to ensure proper order
        df = df.sort_values('Date').reset_index(drop=True)
        
        # Get opening balance
        opening_balance, _ = self._extract_opening_closing_balances()
        if opening_balance is None:
            opening_balance = 0
        
        # Calculate running balance
        running_balance = opening_balance
        df['Running_Balance'] = 0.0
        
        for idx, row in df.iterrows():
            withdrawals = float(row.get('Withdrawals', 0)) if pd.notna(row.get('Withdrawals')) else 0
            deposits = float(row.get('Deposits', 0)) if pd.notna(row.get('Deposits')) else 0
            net_change = deposits - withdrawals
            
            running_balance += net_change
            df.at[idx, 'Running_Balance'] = running_balance
        
        return df
    
    def _analyze_removed_transactions_dp(self, removed_transactions, target_amount, raw_diff):
        """
        Use dynamic programming to analyze removed transactions
        
        Args:
            removed_transactions: DataFrame of dropped rows
            target_amount: absolute size of the mismatch
            raw_diff: signed mismatch
                >0 means we ended too LOW → probably missing a DEPOSIT
                <0 means we ended too HIGH → probably missing a WITHDRAWAL
        """
        print(f"    🔍 Analyzing {len(removed_transactions)} removed transactions...")
        
        need_deposit = raw_diff > 0
        need_withdrawal = raw_diff < 0
        
        print(f"    📊 Direction analysis: raw_diff={raw_diff:+.2f}")
        if need_deposit:
            print(f"    💡 We're too LOW - looking for missing DEPOSITS")
        elif need_withdrawal:
            print(f"    💡 We're too HIGH - looking for missing WITHDRAWALS")
        
        # Get all removed transaction amounts, filtered by direction
        amounts = []
        for idx, row in removed_transactions.iterrows():
            withdrawals = float(row.get('Withdrawals', 0)) if pd.notna(row.get('Withdrawals')) else 0
            deposits = float(row.get('Deposits', 0)) if pd.notna(row.get('Deposits')) else 0
            
            if withdrawals > 0 and need_withdrawal:
                amounts.append(('withdrawal', idx, withdrawals, row['Description']))
            if deposits > 0 and need_deposit:
                amounts.append(('deposit', idx, deposits, row['Description']))
        
        print(f"    📊 Found {len(amounts)} candidate amounts in removed transactions matching needed direction")
        
        # Look for exact matches first
        tolerance = 0.01
        exact_matches = []
        
        for amount_type, idx, amount, description in amounts:
            if abs(amount - target_amount) <= tolerance:
                exact_matches.append((amount_type, idx, amount, description))
        
        if exact_matches:
            print(f"    ✅ Found {len(exact_matches)} exact matches for ${target_amount:,.2f}:")
            for amount_type, idx, amount, description in exact_matches:
                print(f"      {amount_type}: ${amount:,.2f} - {description}")
                print(f"      💡 This transaction was likely incorrectly removed as a duplicate!")
            
            # Return the exact matches to be added back
            return exact_matches
        else:
            print(f"    ❌ No exact matches found for ${target_amount:,.2f}")
            
            # Look for close matches
            close_matches = []
            for amount_type, idx, amount, description in amounts:
                if abs(amount - target_amount) <= 10:  # Within $10
                    close_matches.append((amount_type, idx, amount, description))
            
            if close_matches:
                print(f"    🔍 Found {len(close_matches)} close matches (within $10):")
                for amount_type, idx, amount, description in close_matches:
                    diff = abs(amount - target_amount)
                    print(f"      {amount_type}: ${amount:,.2f} - {description} (diff: ${diff:,.2f})")
            
            # Try combinations of removed transactions
            if len(amounts) <= 10:  # Only for small sets
                print(f"    🔍 Checking combinations of removed transactions...")
                combinations = self._find_removed_transaction_combinations(amounts, target_amount)
                if combinations:
                    return combinations
            
            return None
    
    def _find_removed_transaction_combinations(self, amounts, target_amount):
        """Find combinations of removed transactions that could explain the balance difference"""
        tolerance = 0.01
        close_combinations = []
        
        # Check pairs
        for i, (type1, idx1, amount1, desc1) in enumerate(amounts):
            for j, (type2, idx2, amount2, desc2) in enumerate(amounts[i+1:], i+1):
                total = amount1 + amount2
                if abs(total - target_amount) <= tolerance:
                    close_combinations.append((total, [
                        (type1, idx1, amount1, desc1),
                        (type2, idx2, amount2, desc2)
                    ]))
        
        if close_combinations:
            print(f"    ✅ Found {len(close_combinations)} combinations of removed transactions:")
            for sum_val, combination in close_combinations[:3]:
                print(f"      Total: ${sum_val:,.2f}")
                for amount_type, idx, amount, description in combination:
                    print(f"        {amount_type}: ${amount:,.2f} - {description}")
            
            # Return the first combination to be added back
            return close_combinations[0][1]  # Return the transaction list
        else:
            print(f"    ❌ No combinations of removed transactions found")
            return None
    
    def _find_transaction_combinations(self, df, target_amount):
        """Find combinations of transactions that could explain the balance difference"""
        print(f"    🔍 Looking for transaction combinations totaling ${target_amount:,.2f}...")
        
        # Get all transaction amounts (limit to reasonable number for performance)
        amounts = []
        for idx, row in df.iterrows():
            withdrawals = float(row.get('Withdrawals', 0)) if pd.notna(row.get('Withdrawals')) else 0
            deposits = float(row.get('Deposits', 0)) if pd.notna(row.get('Deposits')) else 0
            if withdrawals > 0:
                amounts.append(('withdrawal', idx, withdrawals, row['Description']))
            if deposits > 0:
                amounts.append(('deposit', idx, deposits, row['Description']))
        
        # Limit to first 20 amounts for performance
        if len(amounts) > 20:
            print(f"    ⚠️  Limiting to first 20 transactions for performance (total: {len(amounts)})")
            amounts = amounts[:20]
        
        # Simple approach: look for exact matches first
        tolerance = 0.01
        close_combinations = []
        
        # Check single transactions first
        for amount_type, idx, amount, description in amounts:
            if abs(amount - target_amount) <= tolerance:
                close_combinations.append((amount, [(amount_type, idx, amount, description)]))
        
        # Check pairs if no single matches found
        if not close_combinations:
            for i, (type1, idx1, amount1, desc1) in enumerate(amounts):
                for j, (type2, idx2, amount2, desc2) in enumerate(amounts[i+1:], i+1):
                    total = amount1 + amount2
                    if abs(total - target_amount) <= tolerance:
                        close_combinations.append((total, [
                            (type1, idx1, amount1, desc1),
                            (type2, idx2, amount2, desc2)
                        ]))
        
        if close_combinations:
            print(f"    ✅ Found {len(close_combinations)} combinations close to target:")
            for sum_val, combination in close_combinations[:3]:  # Show first 3
                print(f"      Total: ${sum_val:,.2f}")
                for amount_type, idx, amount, description in combination:
                    print(f"        {amount_type}: ${amount:,.2f} - {description}")
        else:
            print(f"    ❌ No combinations found close to target amount")
            print(f"    💡 This suggests the missing transaction is not in the current data")
    
    
    def _extract_opening_closing_balances(self):
        """Extract opening and closing balances from the PDF"""
        bank = (self.metadata.get('bank') or '').upper()
        is_credit_card = self.metadata.get('is_credit_card', False)
        
        # SCOTIA VISA: Extract from Table 1 using Camelot
        if is_credit_card and bank == 'SCOTIABANK':
            try:
                import camelot
                all_tables = camelot.read_pdf(self.pdf_path, pages="all", flavor="stream")
                opening_balance = None
                closing_balance = None
                
                for table_idx, table in enumerate(all_tables):
                    df = table.df.fillna('')
                    for idx in range(len(df)):
                        row = df.iloc[idx]
                        row_text = ' '.join([str(cell) for cell in row.tolist()])
                        row_text_upper = row_text.upper()
                        
                        # Look for "Previous balance" - opening balance
                        if 'PREVIOUS BALANCE' in row_text_upper and opening_balance is None:
                            amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                            if amount_match:
                                try:
                                    opening_balance = float(amount_match.group(1).replace(',', ''))
                                    print(f"    📊 Scotia Visa: Found opening balance: ${opening_balance:,.2f}")
                                except:
                                    pass
                        
                        # Look for "New Balance" or "Account Balance" - closing balance
                        if ('NEW BALANCE' in row_text_upper or 'ACCOUNT BALANCE' in row_text_upper) and closing_balance is None:
                            amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                            if amount_match:
                                try:
                                    closing_balance = float(amount_match.group(1).replace(',', ''))
                                    print(f"    📊 Scotia Visa: Found closing balance: ${closing_balance:,.2f}")
                                except:
                                    pass
                
                if opening_balance is not None or closing_balance is not None:
                    return opening_balance, closing_balance
            except Exception as e:
                print(f"Warning: Could not extract Scotia Visa balances from tables: {e}")
        
        # SCOTIABANK BANK ACCOUNT: Use opening balance from BALANCE FORWARD if available
        # Closing balance will be extracted from last transaction's Balance column in _verify_running_balance
        if bank == 'SCOTIABANK' and not is_credit_card and self.metadata.get('scotiabank_opening_balance_from_bf') is not None:
            opening_balance = self.metadata.get('scotiabank_opening_balance_from_bf')
            closing_balance = None  # Will be extracted from last transaction's Balance column
        else:
            opening_balance = None
            closing_balance = None
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                # Check first few pages for balance information
                for page_num in range(min(3, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    if text:
                        # Normalize some whitespace and currency formatting noise to help regex
                        norm = text
                        norm = re.sub(r"\s+", " ", norm)
                        norm = norm.replace("C$", "$")
                        norm = norm.replace("USD$", "$")
                        norm = norm.replace("CAD$", "$")
                        # Sometimes colon or equals used: unify to space
                        norm = norm.replace(":", " ").replace("=", " ")
                        
                        # Bank-specific patterns (check first before generic patterns)
                        if bank == 'CIBC':
                            # Look for "Opening balance on Nov 1, 2023 $24,142.56"
                            cibc_open_match = re.search(r'Opening\s+balance\s+on\s+\w+\s+\d+,\s*\d{4}\s+\$?([\d,]+\.?\d*)', norm, re.IGNORECASE)
                            if cibc_open_match:
                                opening_balance = float(cibc_open_match.group(1).replace(',', ''))
                            
                            # Look for "Closing balance on Nov 30, 2023 = $43,605.77"
                            # Note: norm already replaced "=" with space, so look for both patterns
                            cibc_close_match = re.search(r'Closing\s+balance\s+on\s+\w+\s+\d+,\s*\d{4}\s+\$?([\d,]+\.?\d*)', norm, re.IGNORECASE)
                            if cibc_close_match:
                                closing_balance = float(cibc_close_match.group(1).replace(',', ''))
                            
                            if opening_balance and closing_balance:
                                break
                            # Continue to generic patterns if CIBC-specific didn't match
                        
                        # RBC-specific patterns (check before generic patterns)
                        if bank == 'RBC':
                            # RBC text is often extracted without spaces: "OpeningbalanceonDecember11,2020 $2,245.89" or "-$1,345.99"
                            # Pattern must match with or without spaces and handle negative balances
                            # Look for "Opening balance on [Month] [day], [year] -?$[amount]" or "Openingbalanceon[Month][day],[year] -?$[amount]"
                            # Must have $ sign before amount to avoid matching dates
                            # Handle negative balances: "OpeningbalanceonMarch31,2023 -$1,345.99"
                            rbc_open_match = re.search(r'Opening\s*balance\s*on\s*\w+\s*\d+,\s*\d{4}\s+-?\$\s*([\d,]+\.\d{2})', norm, re.IGNORECASE)
                            if rbc_open_match:
                                amount_str = rbc_open_match.group(1).replace(',', '')
                                # Check if the balance is negative by looking at the full match
                                full_match = rbc_open_match.group(0)
                                is_negative = '-' in full_match
                                opening_balance = float(amount_str)
                                if is_negative:
                                    opening_balance = -opening_balance
                            
                            # Look for "Closing balance on [Month] [day], [year] = -?$[amount]" or "Closingbalanceon[Month][day],[year] -?$[amount]"
                            # Note: norm already replaced "=" with space
                            rbc_close_match = re.search(r'Closing\s*balance\s*on\s*\w+\s*\d+,\s*\d{4}\s+-?\$\s*([\d,]+\.\d{2})', norm, re.IGNORECASE)
                            if rbc_close_match:
                                amount_str = rbc_close_match.group(1).replace(',', '')
                                # Check if the balance is negative by looking at the full match
                                full_match = rbc_close_match.group(0)
                                is_negative = '-' in full_match
                                closing_balance = float(amount_str)
                                if is_negative:
                                    closing_balance = -closing_balance
                            
                            if opening_balance is not None and closing_balance is not None:
                                break
                            # Continue to generic patterns if RBC-specific didn't match
                        
                        # Look for opening balance patterns
                        opening_patterns = [
                            # Generic
                            r'Opening\s*balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            r'Beginning\s*balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            r'Previous\s*balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            r'Balance\s*Forward[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            # RBC variants (legacy patterns for old format)
                            r'Openingbalanceon[^\d]*-\$([\d,]+\.?\d*)',
                            r'Openingbalanceon[^\d]*\$([\d,]+\.?\d*)',
                            # TD variants
                            r'Balance\s*from\s*previous\s*statement[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            r'Balance\s*Brought\s*Forward[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            # Scotiabank variants
                            r'Previous\s*Account\s*Balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            # BMO variants
                            r'BALANCE\s*FORWARD[^\d\-]*-?\$?([\d,]+\.?\d*)',
                        ]
                        
                        for pattern in opening_patterns:
                            matches = re.findall(pattern, norm, re.IGNORECASE)
                            if matches:
                                opening_balance = float(matches[0].replace(',', ''))
                                # Check if this was a negative balance pattern
                                if r'-\$' in pattern:
                                    opening_balance = -opening_balance
                                break
                        
                        # Look for closing balance patterns
                        closing_patterns = [
                            # Generic
                            r'Closing\s*balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            r'Ending\s*balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            r'Current\s*balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            # RBC variants (legacy patterns for old format)
                            r'Closingbalanceon[^\d]*-\$([\d,]+\.?\d*)',
                            r'Closingbalanceon[^\d]*\$([\d,]+\.?\d*)',
                            # TD variants
                            r'New\s*balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            r'Closing\s*Balance\s*as\s*of[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            r'New\s*Account\s*Balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            # Scotiabank variants
                            r'Closing\s*Account\s*Balance[^\d\-]*-?\$?([\d,]+\.?\d*)',
                            # BMO variants
                            r'NEW\s*BALANCE[^\d\-]*-?\$?([\d,]+\.?\d*)',
                        ]
                        
                        for pattern in closing_patterns:
                            matches = re.findall(pattern, norm, re.IGNORECASE)
                            if matches:
                                closing_balance = float(matches[0].replace(',', ''))
                                # Check if this was a negative balance pattern
                                if r'-\$' in pattern:
                                    closing_balance = -closing_balance
                                break
                        
                        if opening_balance and closing_balance:
                            break
                
                return opening_balance, closing_balance
        except Exception as e:
            print(f"Warning: Could not extract balances: {e}")
        
        return None, None
    
    def _parse_date(self, date_str):
        """
        Parse various date formats to datetime
        """
        if pd.isna(date_str) or date_str == '' or date_str == 'None':
            return None
        
        try:
            date_str = str(date_str).strip()
            
            # Try common formats
            # Format 1: Jan 15, 2024 or Nov 07 or NOV01 (TD format - uppercase no space)
            if re.match(r'[A-Z][a-z]{2}\s+\d{1,2}', date_str) or re.match(r'[A-Z]{3}\d{1,2}', date_str):
                # For TD format (NOV01), add space between month and day
                if re.match(r'[A-Z]{3}\d{1,2}', date_str):
                    # Split into month and day: "NOV01" -> "NOV 01"
                    month = date_str[:3]
                    day = date_str[3:]
                    date_str = f"{month} {day}"
                
                # Add year if not present
                if not re.search(r'\d{4}', date_str):
                    # Use statement year from metadata if available, otherwise current year
                    year = str(self.metadata.get('statement_year', '2023'))  # Ensure string
                    date_str = f"{date_str} {year}"
                return date_parser.parse(date_str)
            
            # Format 2: 01/15 or 01/15/2024 or 01/15/24 → normalize; CIBC uses MM/DD formats
            elif '/' in date_str:
                bank = (self.metadata.get('bank') or '').upper()
                if re.match(r'^\d{1,2}/\d{1,2}(/\d{2,4})?$', date_str.strip()):
                    yr = str(self.metadata.get('statement_year', '2023'))  # Ensure string
                    # If year absent or 2-digit, force to statement_year
                    parts = date_str.strip().split('/')
                    if len(parts) == 2:
                        mm, dd = parts
                        norm = f"{yr}-{int(mm):02d}-{int(dd):02d}"
                        return date_parser.parse(norm)
                    elif len(parts) == 3:
                        mm, dd, yy = parts
                        # If year is 2-digit or doesn't match statement_year, use statement_year
                        if len(yy) <= 2 or int(yy) < 2015 or int(yy) > 2035:
                            norm = f"{yr}-{int(mm):02d}-{int(dd):02d}"
                        else:
                            norm = f"{yy}-{int(mm):02d}-{int(dd):02d}"
                        return date_parser.parse(norm)
                # Fallback: parse as-is (but try to apply statement_year if no year)
                parsed = date_parser.parse(date_str)
                # If parsed year seems wrong (before 2015), try applying statement_year
                if parsed and parsed.year < 2015:
                    yr = str(self.metadata.get('statement_year', '2023'))
                    # Try to extract month/day and reconstruct with statement_year
                    if '/' in date_str:
                        parts = date_str.strip().split('/')
                        if len(parts) >= 2:
                            mm, dd = parts[0], parts[1]
                            norm = f"{yr}-{int(mm):02d}-{int(dd):02d}"
                            return date_parser.parse(norm)
                return parsed
            
            # Format 3: 2024-01-15
            elif '-' in date_str:
                return date_parser.parse(date_str)
            
            # Format 4: RBC/BMO format like "01 Mar" or "Mar 01"
            elif re.match(r'(\d{1,2}\s+[A-Za-z]{3}|[A-Za-z]{3}\s+\d{1,2})$', date_str.strip()):
                # Use the RBC date converter which handles the year correctly
                converted_date = self._convert_rbc_date(date_str)
                return date_parser.parse(converted_date)
            
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
        
        # Ensure bank is detected and normalized
        if not self.metadata.get('bank'):
            # Try to detect from PDF text if not already detected
            import pdfplumber
            with pdfplumber.open(self.pdf_path) as pdf:
                sample_text = pdf.pages[0].extract_text() if pdf.pages else ""
            self._detect_bank(sample_text)
        
        # Normalize bank name for Scotiabank
        bank = (self.metadata.get('bank') or '').upper()
        if 'scotia' in bank.lower() or 'nova scotia' in bank.lower():
            self.metadata['bank'] = 'Scotiabank'  # Normalize to 'Scotiabank'
            print(f"  Bank detected as: Scotiabank")
        
        camelot_transactions = []
        text_transactions = []
        
        try:
            import camelot
            
            # Step 1: Get Camelot table structure for better parsing
            tables_stream = camelot.read_pdf(self.pdf_path, pages='all', flavor='stream')
            
            # Fallback bank detection from table structure if not already detected
            if not self.metadata.get('bank') and tables_stream:
                # Detect from table structure (Scotiabank has specific header patterns)
                for i, table in enumerate(tables_stream[:5]):  # Check first 5 tables
                    df_check = table.df.fillna('')
                    table_text = ' '.join(df_check.astype(str).values.flatten()).lower()
                    
                    # Check for Scotiabank-specific patterns in the table
                    # Look for "Bank of Nova Scotia" or "Scotiabank" in table content
                    if 'bank of nova scotia' in table_text or 'scotiabank' in table_text:
                        self.metadata['bank'] = 'Scotiabank'
                        print(f"  Bank detected as: Scotiabank (from table content)")
                        break
                    
                    # Check for Scotiabank-specific header patterns
                    for idx, row in df_check.iterrows():
                        if idx > 10:  # Check first 10 rows
                            break
                        row_text = ' '.join([str(cell) for cell in row.tolist()]).lower()
                        # Check for Scotiabank-specific header patterns
                        if (('withdrawals/debits' in row_text or 'deposits/credits' in row_text) and 'balance ($)' in row_text) or \
                           ('d ate' in row_text and 'description' in row_text and ('withdrawal' in row_text or 'debit' in row_text) and 'balance' in row_text):
                            self.metadata['bank'] = 'Scotiabank'
                            print(f"  Bank detected as: Scotiabank (from table structure)")
                            break
                    if self.metadata.get('bank') == 'Scotiabank':
                        break
            
            if tables_stream:
                print(f"Camelot found {len(tables_stream)} tables with stream mode")
                
                # Re-check bank after table detection (might have been detected from table structure)
                bank = (self.metadata.get('bank') or '').upper()
                
                # Check if this is a credit card statement
                is_credit_card = self.metadata.get('is_credit_card', False)
                
                # Look for transaction tables and extract structure info
                transaction_table_info = []
                
                # For Scotia Visa credit cards, look for credit card transaction tables
                if is_credit_card and bank == 'SCOTIABANK':
                    print(f"  Scotia Visa: Scanning all {len(tables_stream)} tables for credit card transaction headers...")
                    for i, table in enumerate(tables_stream):
                        df = table.df.fillna('')
                        if len(df) == 0:
                            continue
                        
                        # Check if this table has credit card transaction headers
                        for idx, row in df.iterrows():
                            if idx > 10:  # Only check first 10 rows
                                break
                            row_text = ' '.join([str(cell).replace('\n', ' ').replace('\r', ' ') for cell in row.tolist()]).upper()
                            # Look for "REF.#" and "AMOUNT($)" headers (credit card format)
                            if 'REF.#' in row_text and 'AMOUNT' in row_text:
                                print(f"  Table {i+1} appears to be a credit card transaction table (Scotia Visa) - header at row {idx}")
                                transaction_table_info.append({
                                    'table': df,
                                    'page': getattr(table, 'page', 1) if hasattr(table, 'page') else 1
                                })
                                break
                
                # For Scotiabank bank accounts, use dynamic table detection (scan all tables for transaction headers)
                # This matches the working debug script logic
                # Also check if tables have Scotiabank-style headers even if bank not detected yet
                is_scotiabank_style = False
                if bank == 'SCOTIABANK' and not is_credit_card:
                    is_scotiabank_style = True
                else:
                    # Check if tables have Scotiabank-style headers (fallback detection)
                    for i, table in enumerate(tables_stream[:5]):
                        df_check = table.df.fillna('')
                        for idx, row in df_check.iterrows():
                            if idx > 10:
                                break
                            row_text = ' '.join([str(cell) for cell in row.tolist()]).lower()
                            if (('withdrawals/debits' in row_text or 'deposits/credits' in row_text) and 'balance ($)' in row_text) or \
                               ('d ate' in row_text and 'description' in row_text and ('withdrawal' in row_text or 'debit' in row_text) and 'balance' in row_text):
                                is_scotiabank_style = True
                                if not self.metadata.get('bank'):
                                    self.metadata['bank'] = 'Scotiabank'
                                    bank = 'SCOTIABANK'
                                    print(f"  Bank detected as: Scotiabank (from table headers)")
                                break
                        if is_scotiabank_style:
                            break
                
                if is_scotiabank_style:
                    print(f"  Scotiabank: Scanning all {len(tables_stream)} tables for transaction headers...")
                    for i, table in enumerate(tables_stream):
                        df = table.df.fillna('')
                        if len(df) == 0:
                            continue
                        
                        # Check if this table has transaction headers (same logic as debug script)
                        header_row_idx = None
                        column_headers = None
                        for idx, row in df.iterrows():
                            if idx > 10:  # Only check first 10 rows
                                break
                            row_text = ' '.join([str(cell).replace('\n', ' ').replace('\r', ' ') for cell in row.tolist()]).lower()
                            if ('date' in row_text or 'd ate' in row_text) and 'description' in row_text and ('debit' in row_text or 'withdrawal' in row_text or 'credit' in row_text or 'deposit' in row_text):
                                header_row_idx = idx
                                column_headers = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
                                print(f"  Table {i+1} appears to be a transaction table (Scotiabank) - header at row {header_row_idx}")
                                transaction_table_info.append({
                                    'table': df,
                                    'page': getattr(table, 'page', 1) if hasattr(table, 'page') else 1
                                })
                                break
                else:
                    # For other banks, use existing logic
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
                        # Use Scotia Visa-specific parsing if credit card
                        if is_credit_card and bank == 'SCOTIABANK':
                            table_transactions = self._parse_camelot_transactions_scotia_visa(table_info['table'])
                            if isinstance(table_transactions, pd.DataFrame) and not table_transactions.empty:
                                all_camelot_transactions.extend(table_transactions.to_dict('records'))
                        # Use Scotiabank bank account-specific parsing
                        elif bank == 'SCOTIABANK' and not is_credit_card:
                            table_transactions = self._parse_camelot_transactions_scotiabank(table_info['table'])
                            if isinstance(table_transactions, pd.DataFrame) and not table_transactions.empty:
                                all_camelot_transactions.extend(table_transactions.to_dict('records'))
                        else:
                            table_transactions = self._parse_camelot_transactions(table_info['table'])
                            if isinstance(table_transactions, pd.DataFrame) and not table_transactions.empty:
                                all_camelot_transactions.extend(table_transactions.to_dict('records'))
                    
                    # Deduplicate Camelot transactions before proceeding
                    if all_camelot_transactions:
                        camelot_df = pd.DataFrame(all_camelot_transactions)
                        
                        # For RBC statements, don't deduplicate - keep all transactions
                        # RBC statements can have legitimate duplicate transactions
                        bank = (self.metadata.get('bank') or '').upper()
                        is_credit_card = self.metadata.get('is_credit_card', False)
                        
                        if bank == 'RBC':
                            print(f"Camelot RBC: Keeping all {len(camelot_df)} transactions (no deduplication)")
                            camelot_transactions = camelot_df.to_dict('records')
                        elif is_credit_card and bank == 'SCOTIABANK':
                            # For Scotia Visa credit cards, use Amount column for deduplication
                            if 'Amount' in camelot_df.columns:
                                before_dedup = len(camelot_df)
                                camelot_df = camelot_df.drop_duplicates(subset=['Date', 'Description', 'Amount'])
                                removed = before_dedup - len(camelot_df)
                                if removed > 0:
                                    print(f"Camelot Scotia Visa: Removed {removed} duplicates using Amount column")
                                else:
                                    print(f"Camelot Scotia Visa: No duplicates found (using Amount column)")
                            camelot_transactions = camelot_df.to_dict('records')
                            print(f"After Camelot deduplication: {len(camelot_transactions)} unique transactions")
                        elif bank == 'SCOTIABANK':
                            # For Scotiabank, use Balance column for deduplication
                            if 'Balance' in camelot_df.columns:
                                before_dedup = len(camelot_df)
                                camelot_df = camelot_df.drop_duplicates(subset=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'])
                                removed = before_dedup - len(camelot_df)
                                if removed > 0:
                                    print(f"Camelot Scotiabank: Removed {removed} duplicates using Balance column")
                                else:
                                    print(f"Camelot Scotiabank: No duplicates found (using Balance column for deduplication)")
                            else:
                                print(f"Camelot Scotiabank: No Balance column found, using standard deduplication")
                                camelot_df = camelot_df.drop_duplicates(subset=['Date', 'Description', 'Withdrawals', 'Deposits'])
                            camelot_transactions = camelot_df.to_dict('records')
                            print(f"After Camelot deduplication: {len(camelot_transactions)} unique transactions")
                        else:
                            # For other banks, use deduplication; prefer Balance-aware when available
                            if 'Balance' in camelot_df.columns:
                                camelot_df = camelot_df.drop_duplicates(subset=['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance'])
                                print(f"Camelot deduplication: Using Balance column to preserve transactions with different balances")
                            else:
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
    
    def _find_column_indices_scotiabank(self, column_headers):
        """Find column indices for Date, Description, Withdrawals, Deposits, Balance from headers - SCOTIABANK ONLY"""
        indices = {
            'date': None,
            'description': None,
            'withdrawal': None,
            'deposit': None,
            'balance': None
        }
        
        for idx, header in enumerate(column_headers):
            header_lower = str(header).lower().replace('\n', ' ').replace('\r', ' ')
            if 'date' in header_lower or 'd ate' in header_lower:
                indices['date'] = idx
            elif 'description' in header_lower:
                indices['description'] = idx
            elif ('withdrawal' in header_lower or 'debit' in header_lower) and indices['withdrawal'] is None:
                indices['withdrawal'] = idx
            elif ('deposit' in header_lower or 'credit' in header_lower) and indices['deposit'] is None:
                indices['deposit'] = idx
            elif 'balance' in header_lower:
                indices['balance'] = idx
        
        # Balance is often in the last column if not explicitly found
        if indices['balance'] is None and len(column_headers) > 0:
            indices['balance'] = len(column_headers) - 1
        
        return indices

    def _parse_camelot_transactions_scotiabank(self, df):
        """Parse transactions from Camelot-extracted DataFrame - SCOTIABANK SPECIFIC"""
        transactions = []
        opening_balance_from_bf = None
        current_transaction = None
        pending_description_parts = []
        
        # Clean the DataFrame
        df = df.fillna('')
        
        # Find header row dynamically
        header_row_idx = None
        column_headers = None
        for idx, row in df.iterrows():
            row_text = ' '.join([str(cell).replace('\n', ' ').replace('\r', ' ') for cell in row.tolist()]).lower()
            if ('date' in row_text or 'd ate' in row_text) and 'description' in row_text and ('debit' in row_text or 'withdrawal' in row_text or 'credit' in row_text or 'deposit' in row_text):
                header_row_idx = idx
                column_headers = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
                break
        
        if header_row_idx is None:
            # No header found, return empty
            print("  Scotiabank: No header row found in table")
            return pd.DataFrame()
        
        print(f"  Scotiabank: Found header at row {header_row_idx}: {column_headers}")
        
        # Find column indices from headers
        col_indices = self._find_column_indices_scotiabank(column_headers)
        date_idx = col_indices['date']
        desc_idx = col_indices['description']
        withdrawal_idx = col_indices['withdrawal']
        deposit_idx = col_indices['deposit']
        balance_idx = col_indices['balance']
        
        print(f"  Scotiabank: Column indices - Date: {date_idx}, Desc: {desc_idx}, Withdrawal: {withdrawal_idx}, Deposit: {deposit_idx}, Balance: {balance_idx}")
        
        # Process rows after header
        rows_processed = 0
        for idx in range(header_row_idx + 1, len(df)):
            row = df.iloc[idx]
            row_list = [str(cell).replace('\n', '').replace('\r', '').strip() for cell in row.tolist()]
            
            if not any(row_list):
                continue
            
            rows_processed += 1
            if rows_processed <= 3:  # Debug first 3 rows
                print(f"  Scotiabank: Processing row {idx}: {row_list[:5]}...")
            
            # Check if this is BALANCE FORWARD row (extract opening balance but don't add as transaction)
            row_text = ' '.join(row_list).upper()
            if 'BALANCE FORWARD' in row_text:
                # Extract balance from balance column
                if balance_idx is not None and balance_idx < len(row_list):
                    balance_str = row_list[balance_idx]
                    if balance_str:
                        # Handle trailing minus (negative balance)
                        is_negative = balance_str.strip().endswith('-')
                        balance_clean = balance_str.replace(',', '').replace('-', '').strip()
                        if re.match(r'^[\d,]+\.?\d{0,2}$', balance_clean):
                            opening_balance_from_bf = float(balance_clean)
                            if is_negative:
                                opening_balance_from_bf = -opening_balance_from_bf
                continue  # Skip this row, don't add as transaction
            
            # Extract date
            date_match = None
            if date_idx is not None and date_idx < len(row_list):
                date_cell = row_list[date_idx]
                cleaned_date = date_cell.strip()
                # Remove leading '0 ' or '1 ' followed by space
                if cleaned_date.startswith('0 ') or cleaned_date.startswith('1 '):
                    cleaned_date = cleaned_date[2:].strip()
                # Check for MM/DD/YYYY format
                if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', cleaned_date):
                    date_match = cleaned_date
            
            if date_match:
                # Save previous transaction
                if current_transaction:
                    if pending_description_parts:
                        current_transaction['Description'] = ' '.join(pending_description_parts) + ' ' + current_transaction.get('Description', '')
                        current_transaction['Description'] = ' '.join(current_transaction['Description'].split())
                    transactions.append(current_transaction)
                
                # Extract new transaction
                description = row_list[desc_idx] if desc_idx is not None and desc_idx < len(row_list) else ''
                withdrawal = None
                deposit = None
                balance = None
                
                # Extract amounts from detected column positions
                if withdrawal_idx is not None and withdrawal_idx < len(row_list):
                    withdrawal_str = row_list[withdrawal_idx]
                    if withdrawal_str and re.match(r'^[\d,]+\.?\d{0,2}$', withdrawal_str.replace(',', '')):
                        withdrawal = float(withdrawal_str.replace(',', ''))
                
                if deposit_idx is not None and deposit_idx < len(row_list):
                    deposit_str = row_list[deposit_idx]
                    if deposit_str and re.match(r'^[\d,]+\.?\d{0,2}$', deposit_str.replace(',', '')):
                        deposit = float(deposit_str.replace(',', ''))
                
                # If amounts not found in expected columns, scan all columns (handles empty columns in Table 2)
                if withdrawal is None and deposit is None:
                    for col_idx, cell in enumerate(row_list):
                        if col_idx == date_idx or col_idx == desc_idx or col_idx == balance_idx:
                            continue  # Skip date, description, and balance columns
                        cell_clean = str(cell).replace(',', '').strip()
                        if cell_clean and re.match(r'^[\d,]+\.?\d{0,2}$', cell_clean):
                            amount = float(cell_clean)
                            # If we're before the deposit column, it's likely a withdrawal
                            # If we're after the description, check if it's in withdrawal or deposit range
                            if withdrawal_idx is not None and col_idx < deposit_idx if deposit_idx is not None else True:
                                withdrawal = amount
                            elif deposit_idx is not None and col_idx >= deposit_idx:
                                deposit = amount
                            else:
                                # Default: if no deposit found yet, assume withdrawal
                                withdrawal = amount
                            break
                
                if balance_idx is not None and balance_idx < len(row_list):
                    balance_str = row_list[balance_idx]
                    if balance_str:
                        # Handle trailing minus (negative balance)
                        is_negative = balance_str.strip().endswith('-')
                        balance_clean = balance_str.replace(',', '').replace('-', '').strip()
                        if re.match(r'^[\d,]+\.?\d{0,2}$', balance_clean):
                            balance = float(balance_clean)
                            if is_negative:
                                balance = -balance
                
                # Convert date to YYYY-MM-DD format
                try:
                    date_parts = date_match.split('/')
                    if len(date_parts) == 3:
                        month, day, year = date_parts
                        converted_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        converted_date = date_match
                except:
                    converted_date = date_match
                
                current_transaction = {
                    'Date': converted_date,
                    'Description': description,
                    'Withdrawals': withdrawal,
                    'Deposits': deposit,
                    'Balance': balance
                }
                pending_description_parts = []
            else:
                # Continuation row - add to description
                if current_transaction and desc_idx is not None and desc_idx < len(row_list):
                    desc_part = row_list[desc_idx]
                    if desc_part:
                        pending_description_parts.append(desc_part)
        
        # Save last transaction
        if current_transaction:
            if pending_description_parts:
                current_transaction['Description'] = ' '.join(pending_description_parts) + ' ' + current_transaction.get('Description', '')
                current_transaction['Description'] = ' '.join(current_transaction['Description'].split())
            transactions.append(current_transaction)
        
        # Store opening balance in metadata for later use
        if opening_balance_from_bf is not None:
            self.metadata['scotiabank_opening_balance_from_bf'] = opening_balance_from_bf
        
        if transactions:
            return pd.DataFrame(transactions)
        return pd.DataFrame()
    
    def _parse_camelot_transactions_scotia_visa(self, df):
        """Parse transactions from Camelot-extracted DataFrame - SCOTIA VISA CREDIT CARD SPECIFIC"""
        transactions = []
        
        # Clean the DataFrame
        df = df.fillna('')
        
        # Month mapping for date parsing
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        # Get statement years for date conversion
        # Convert to int if they exist, otherwise use defaults
        statement_start_year = self.metadata.get('statement_start_year')
        statement_end_year = self.metadata.get('statement_end_year')
        
        # If not set, try to get from statement_year
        if not statement_start_year:
            statement_start_year = self.metadata.get('statement_year', '2024')
        if not statement_end_year:
            statement_end_year = self.metadata.get('statement_year', '2024')
        
        # Ensure they're strings for comparison (they come from regex groups)
        statement_start_year = str(statement_start_year) if statement_start_year else '2024'
        statement_end_year = str(statement_end_year) if statement_end_year else '2024'
        
        # Find header row (should have "REF.#" and "AMOUNT($)")
        header_row_idx = None
        for idx in range(min(5, len(df))):
            row = df.iloc[idx]
            row_list = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
            row_text = ' '.join(row_list).upper()
            
            if 'REF.#' in row_text and 'AMOUNT' in row_text:
                header_row_idx = idx
                print(f"  Scotia Visa: Found header at row {idx}")
                break
        
        if header_row_idx is None:
            print("  Scotia Visa: No header row found in table")
            return pd.DataFrame()
        
        # Determine start row (check if row after header is account name or transaction)
        check_row = header_row_idx + 1
        if check_row < len(df):
            check_row_text = ' '.join([str(cell) for cell in df.iloc[check_row].tolist()]).upper()
            has_ref_pattern = re.match(r'^\d{3}', str(df.iloc[check_row].iloc[0]).strip())
            start_row = check_row if has_ref_pattern else check_row + 1
        else:
            start_row = check_row
        
        # Process transaction rows
        for idx in range(start_row, len(df)):
            row = df.iloc[idx]
            row_list = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
            
            # Skip empty rows
            if not any(row_list):
                continue
            
            # Skip subtotal rows
            row_text = ' '.join(row_list).upper()
            if 'SUB-TOTAL' in row_text or 'TOTAL' in row_text:
                continue
            
            # Need at least 5 columns
            if len(row_list) < 5:
                continue
            
            ref_str = row_list[0]
            trans_date_str = row_list[1]  # TRANSACTION DATE (when transaction occurred)
            post_date_str = row_list[2]   # POST DATE (when bank processed it)
            description = row_list[3]
            amount_str = row_list[4]
            
            # Validate: REF should be 3 digits
            if not re.match(r'^\d{3}$', ref_str):
                continue
            
            # Parse date (use TRANSACTION DATE - when the transaction actually occurred)
            date_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', trans_date_str, re.IGNORECASE)
            if not date_match:
                continue
            
            month_name = date_match.group(1).lower()
            day = int(date_match.group(2))
            month = month_map.get(month_name, 1)
            
            # Determine which year to use based on month
            if statement_end_year and statement_start_year and statement_start_year != statement_end_year:
                # Statement spans years (e.g., Dec 2024 - Jan 2025)
                # Use end year for Jan-May, start year for Jun-Dec
                if month <= 5:  # Jan-May
                    year_to_use = int(statement_end_year)
                else:  # Jun-Dec
                    year_to_use = int(statement_start_year)
            elif statement_start_year:
                year_to_use = int(statement_start_year)
            else:
                # Fallback: use statement_year from metadata
                year_to_use = int(self.metadata.get('statement_year', '2024'))
            
            # Convert to full date
            try:
                from datetime import datetime
                full_date = datetime(year_to_use, month, day)
                date_str = full_date.strftime('%Y-%m-%d')
            except:
                continue
            
            # Parse amount
            is_negative = amount_str.strip().endswith('-')
            amount_clean = amount_str.replace('-', '').replace('$', '').replace(',', '').strip()
            
            try:
                amount = float(amount_clean)
                if is_negative:
                    amount = -amount
            except:
                continue
            
            # Store transaction (Amount column: positive = charges, negative = payments)
            transactions.append({
                'Date': date_str,
                'Description': description,
                'Amount': amount
            })
        
        if transactions:
            return pd.DataFrame(transactions)
        return pd.DataFrame()

    def _parse_camelot_transactions(self, df):
        """Parse transactions from Camelot-extracted DataFrame - SIMPLIFIED APPROACH"""
        # Check if this is Scotiabank - use specialized parsing
        bank = (self.metadata.get('bank') or '').upper()
        # Also check if bank name contains 'scotia' in case it's detected differently
        if bank == 'SCOTIABANK' or 'scotia' in bank.lower():
            print(f"  Using Scotiabank-specific parsing (bank detected as: {self.metadata.get('bank')})")
            return self._parse_camelot_transactions_scotiabank(df)
        else:
            print(f"  Using standard parsing (bank detected as: {self.metadata.get('bank')})")
        
        transactions = []
        current_date = None
        column_headers = None

        # Clean the DataFrame
        df = df.fillna('')
        
        # Detect column headers from the first few rows
        # For BMO, skip header detection (use simple column-position logic like old working version)
        if bank != 'BMO':
            for idx, row in df.iterrows():
                if idx > 5:  # Only check first 5 rows for headers
                    break
                row_text = ' '.join([str(cell) for cell in row.tolist()]).lower()
                if 'date' in row_text and 'description' in row_text and ('debit' in row_text or 'cheque' in row_text):
                    # This is likely the header row
                    column_headers = [str(cell).strip() for cell in row.tolist()]
                    print(f"Detected column headers: {column_headers}")
                    break
        
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
            # For BMO, ignore headers and use simple column-position logic (like old working version)
            bank = (self.metadata.get('bank') or '').upper()
            if effective_date:
                if bank == 'BMO':
                    # For BMO, don't pass column_headers - use simple column-position logic
                    transaction = self._extract_transaction_from_row_with_date(row_list, effective_date, column_headers=None)
                else:
                    transaction = self._extract_transaction_from_row_with_date(row_list, effective_date, column_headers)
                
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
    
    def _extract_transaction_from_row_with_date(self, row, date, column_headers=None):
        """Extract transaction from row with explicit date"""
        if not date:
            return None
        
        # Create row with date in first position
        row_with_date = [date] + row[1:] if len(row) > 1 else [date]
        return self._extract_transaction_from_row(row_with_date, column_headers)
    
    def _extract_transaction_from_row(self, row, column_headers=None):
        """Extract transaction data from a single row using column headers when available
        For BMO, use simpler column-position-based logic like the old working version to avoid date/transaction mismatches
        """
        if len(row) < 4:  # Need at least Date, Description, Debit, Credit columns
            return None
        
        date = None
        description = None
        debit_amount = None
        credit_amount = None
        balance_amount = None
        
        bank = (self.metadata.get('bank') or '').upper()
        
        # For BMO, always use simple column-position-based extraction (like old working version)
        # The header-based extraction can cause date/transaction mismatches
        # Force BMO to ignore headers and use column positions instead
        if bank == 'BMO':
            # BMO: Simple column-based extraction without headers (like old working commit 6a47aae)
            # The date is already in row[0] from _extract_transaction_from_row_with_date
            # Find date (usually first column with date pattern)
            # Supports both "04 Jan" (RBC) and "Jan 04" (BMO)
            for i, cell in enumerate(row):
                if re.match(r'^(\d{1,2}\s+[A-Za-z]{3}|[A-Za-z]{3}\s+\d{1,2})$', str(cell).strip()):
                    date = cell
                    break
            
            if not date:
                return None
            
            # Find description (usually column 1, longest text field)
            # Allow short descriptions like "PAY" (>= 2 chars, not just > 3)
            description_candidates = [cell for cell in row[1:] if len(str(cell)) >= 2 and not re.match(r'^[\d,.-]+$', str(cell))]
            if description_candidates:
                description = max(description_candidates, key=lambda x: len(str(x)))
                # Clean up newlines and extra spaces
                description = str(description).replace('\n', ' ').strip()
                description = ' '.join(description.split())  # Remove extra spaces
            
            # Look for debit and credit amounts in specific columns (like old working version)
            # Based on Camelot output, amounts can be in columns 2, 3, 4 depending on table structure
            # Strategy: Find the first two columns that contain monetary amounts
            if len(row) >= 3:
                amount_columns = []
                
                # Scan columns 2-5 to find debit and credit columns
                # BMO/RBC formats both have: [Date, Description, Debit(col 2), Credit(col 3), Balance(col 4+)]
                # Stop after finding 2 amount columns to avoid picking up balance
                for col_idx in range(2, min(6, len(row))):
                    col_value = row[col_idx] if col_idx < len(row) else ''
                    if col_value and re.match(r'^[\d,]+\.\d{2}$', str(col_value).replace(',', '')):
                        amount_columns.append((col_idx, col_value))
                        # Stop after finding 2 amount columns to avoid picking up balance
                        if len(amount_columns) == 2:
                            break
                
                # Determine debit and credit based on which columns have amounts (old working logic)
                if len(amount_columns) >= 2:
                    col1_idx = amount_columns[0][0]
                    col2_idx = amount_columns[1][0]
                    
                    # Special case: BMO Table 1 with 4 columns [Date, Desc, Amount, Balance]
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
                                debit_amount = amount_columns[0][1]
                        else:
                            debit_amount = amount_columns[0][1]
                        # Extract balance from column 3
                        balance_amount = amount_columns[1][1]
                    elif col2_idx - col1_idx == 1:
                        # Consecutive columns
                        if col1_idx == 2 and col2_idx == 3:
                            # Columns 2 and 3 - debit and credit
                            debit_amount = amount_columns[0][1]
                            credit_amount = amount_columns[1][1]
                            # Check column 4 for balance
                            if len(row) > 4:
                                potential_balance = row[4] if 4 < len(row) else None
                                if potential_balance and re.match(r'^[\d,]+\.\d{2}$', str(potential_balance).replace(',', '')):
                                    balance_amount = potential_balance
                        elif col1_idx == 3 and col2_idx == 4:
                            # Columns 3 and 4 - first is credit (col 3), second is balance (col 4)
                            credit_amount = amount_columns[0][1]
                            balance_amount = amount_columns[1][1]
                        else:
                            # Default: first is debit, second is credit
                            debit_amount = amount_columns[0][1]
                            credit_amount = amount_columns[1][1]
                elif len(amount_columns) == 1:
                    # Only one amount found - determine if it's debit or credit
                    col_idx, amount = amount_columns[0]
                    
                    # For BMO (4 columns), need to determine if amount is debit or credit based on description
                    if len(row) == 4 and col_idx == 2:
                        # BMO format - use description keywords to classify
                        if description:
                            desc_upper = description.upper()
                            credit_keywords = ['DEPOSIT', 'CREDIT', 'PAYMENT RECEIVED', 'REVERSAL']
                            debit_keywords = ['DEBIT CARD', 'CHEQUE', 'PRE-AUTHORIZED PAYMENT', 'WITHDRAWAL', 
                                             'FEE', 'CHARGE', 'INTERAC', 'E-TRANSFER']
                            
                            is_credit = any(keyword in desc_upper for keyword in credit_keywords)
                            is_debit = any(keyword in desc_upper for keyword in debit_keywords)
                            
                            if is_credit:
                                credit_amount = amount
                            elif is_debit:
                                debit_amount = amount
                            else:
                                debit_amount = amount
                        else:
                            debit_amount = amount
                        # Extract balance from column 3
                        if len(row) > 3:
                            potential_balance = row[3] if 3 < len(row) else None
                            if potential_balance and re.match(r'^[\d,]+\.\d{2}$', str(potential_balance).replace(',', '')):
                                balance_amount = potential_balance
                
                # If still no amounts found, look for amounts in any column (like old working version)
                # This handles edge cases - important for BMO to extract all transactions
                if not debit_amount and not credit_amount:
                    for i in range(len(row)):
                        if i >= 2 and row[i] and re.match(r'^[\d,]+\.\d{2}$', str(row[i]).replace(',', '')):
                            # Determine if this is debit or credit based on description and context
                            if description:
                                desc_upper = description.upper()
                                # Credits (deposits)
                                if any(keyword in desc_upper for keyword in [
                                    'FEDERAL PAYMENT', 'LOAN CREDIT', 'REVERSED CHEQUE', 'REVERSED DEBIT',
                                    'DEPOSIT', 'CREDIT', 'PAYMENT RECEIVED', 'REVERSAL', 'DIRECT DEPOSIT'
                                ]):
                                    credit_amount = row[i]
                                # Debits (withdrawals/fees)
                                elif any(keyword in desc_upper for keyword in [
                                    'FEE', 'CHEQUE OVER', 'ACTIVITY FEE', 'MONTHLY FEE', 'TRANSACTION FEE',
                                    'DEBIT CARD', 'CHEQUE', 'PRE-AUTHORIZED PAYMENT', 'WITHDRAWAL', 
                                    'CHARGE', 'INTERAC', 'E-TRANSFER'
                                ]):
                                    debit_amount = row[i]
                                else:
                                    # Default to debit (withdrawal)
                                    debit_amount = row[i]
                            else:
                                # Default to debit if no description
                                debit_amount = row[i]
                            break
            
            # Convert date to standard format (like old working version)
            if date:
                date = self._convert_rbc_date(date)
            
            # Extract balance if available (usually the last amount column) - like old working version
            if not balance_amount and len(row) >= 4:
                # Look for balance in the last column or second-to-last column
                for i in range(len(row) - 1, max(2, len(row) - 3), -1):  # Check last few columns
                    if row[i] and re.match(r'^[\d,]+\.\d{2}$', str(row[i]).replace(',', '')):
                        # This is likely the balance column
                        balance_amount = row[i]
                        break
            
            # Return transaction if we have date and at least one amount
            # Allow transactions without description (like old working version)
            if date and (debit_amount or credit_amount):
                result = {
                    'Date': date,
                    'Description': description if description else '',
                    'Withdrawals': debit_amount,
                    'Deposits': credit_amount
                }
                if balance_amount:
                    result['Balance'] = balance_amount
                return result
            
            return None
        
        # For other banks, use header-based extraction if available
        # If we have column headers, use them to identify columns
        if column_headers and len(column_headers) == len(row):
            # Find columns by header names
            date_col = None
            desc_col = None
            debit_col = None
            credit_col = None
            
            for i, header in enumerate(column_headers):
                header_lower = header.lower()
                if 'date' in header_lower:
                    date_col = i
                elif 'description' in header_lower:
                    desc_col = i
                elif 'debit' in header_lower or 'cheque' in header_lower:
                    debit_col = i
                elif 'credit' in header_lower or 'deposit' in header_lower:
                    credit_col = i
            
            # Extract data using identified columns
            if date_col is not None:
                date = row[date_col] if date_col < len(row) else None
            
            if desc_col is not None:
                # Combine all contiguous description fragments between 'Description' and first amount column
                # Determine first amount column index among debit/credit/balance-like cells
                first_amount_idx = None
                for i in range(desc_col + 1, len(row)):
                    cell = row[i] or ''
                    if cell and re.match(r'^[\d,]+\.\d{2}$', str(cell).replace(',', '')):
                        first_amount_idx = i
                        break
                if first_amount_idx is None:
                    first_amount_idx = len(row)
                parts = []
                for i in range(desc_col, first_amount_idx):
                    val = str(row[i] or '').strip()
                    if val and not re.match(r'^[\d,]+\.\d{2}$', val.replace(',', '')):
                        parts.append(val)
                description = ' '.join(parts).strip() if parts else None
            
            if debit_col is not None and debit_col < len(row):
                debit_value = row[debit_col]
                if debit_value and re.match(r'^[\d,]+\.\d{2}$', debit_value.replace(',', '')):
                    debit_amount = debit_value
            
            if credit_col is not None and credit_col < len(row):
                credit_value = row[credit_col]
                if credit_value and re.match(r'^[\d,]+\.\d{2}$', credit_value.replace(',', '')):
                    credit_amount = credit_value
        
        # Fallback to original logic if no headers
        else:
            # Find date (usually first column with date pattern)
            # Supports both "04 Jan" (RBC) and "Jan 04" (BMO)
            for i, cell in enumerate(row):
                if re.match(r'^(\d{1,2}\s+[A-Za-z]{3}|[A-Za-z]{3}\s+\d{1,2})$', cell.strip()):
                    date = cell
                    break
        
        if not date:
            return None
        
        # If we used header-based extraction, return the result immediately
        if column_headers and len(column_headers) == len(row):
            # We already extracted using headers, return the result
            if description and (debit_amount or credit_amount):
                return {
                    'Date': date,
                    'Description': description,
                    'Withdrawals': debit_amount,
                    'Deposits': credit_amount
                }
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
        
        # Return transaction if we have date, description, and at least one amount
        if date and description and (debit_amount or credit_amount):
            return {
                'Date': date,
                'Description': description,
                'Withdrawals': debit_amount,
                'Deposits': credit_amount
            }
        
        return None
    
    def _extract_statement_year(self):
        """Extract the statement year from the PDF content"""
        # Check if this is a credit card statement - use specialized extraction
        # Try even if bank not detected yet (credit card detection happens first)
        if self.metadata.get('is_credit_card'):
            # Try Scotia Visa extraction (works even if bank not detected yet)
            try:
                scotia_visa_year = self._extract_statement_year_scotia_visa()
                if scotia_visa_year and scotia_visa_year != '2024':  # If we got a real year (not default)
                    return scotia_visa_year
            except:
                pass  # If extraction fails, fall through to other methods
        
        # Try Scotiabank-specific extraction first (even if bank not detected yet)
        # This works because Scotiabank has a unique table structure
        try:
            scotia_year = self._extract_statement_year_scotiabank()
            if scotia_year and scotia_year != '2023':  # If we got a real year (not default)
                return scotia_year
        except:
            pass  # If Scotiabank extraction fails, fall through to generic extraction
        
        # Check if this is Scotiabank - use specialized extraction
        bank = (self.metadata.get('bank') or '').upper()
        if bank == 'SCOTIABANK':
            return self._extract_statement_year_scotiabank()
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                # Check first few pages for year information
                for page_num in range(min(3, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    if text:
                        # PRIORITY 1: BMO format "For the period ending January 31, 2022"
                        m = re.search(r'For\s+the\s+period\s+ending\s+\w+\s+\d+,\s*(\d{4})', text, re.IGNORECASE)
                        if m:
                            year_str = m.group(1)
                            if 2015 <= int(year_str) <= 2035:
                                print(f"    📅 Extracted statement year from period ending: {year_str}")
                                return year_str
                        
                        # PRIORITY 2: CIBC explicit statement period phrasing like "For Nov 1 to Nov 30, 2023"
                        # Match "For <Month> <day> to <Month> <day>, <year>"
                        m = re.search(r'For\s+\w+\s+\d+\s+to\s+\w+\s+\d+,\s*(\d{4})', text, re.IGNORECASE)
                        if m:
                            year_str = m.group(1)
                            if 2015 <= int(year_str) <= 2035:
                                print(f"    📅 Extracted statement year from period: {year_str}")
                                return year_str
                        
                        # PRIORITY 3: Any "for <Month> <day> to <Month> <day>, <year>" (lowercase)
                        m = re.search(r'for\s+\w+\s+\d+\s+to\s+\w+\s+\d+,\s*(\d{4})', text, re.IGNORECASE)
                        if m:
                            year_str = m.group(1)
                            if 2015 <= int(year_str) <= 2035:
                                print(f"    📅 Extracted statement year from period: {year_str}")
                                return year_str
                        
                        # PRIORITY 4: Opening/Closing balance lines with year
                        m = re.search(r'Opening\s+balance\s+on\s+\w+\s+\d+,\s*(\d{4})', text, re.IGNORECASE)
                        if m:
                            year_str = m.group(1)
                            if 2015 <= int(year_str) <= 2035:
                                print(f"    📅 Extracted statement year from opening balance: {year_str}")
                                return year_str
                        
                        m = re.search(r'Closing\s+balance\s+on\s+\w+\s+\d+,\s*(\d{4})', text, re.IGNORECASE)
                        if m:
                            year_str = m.group(1)
                            if 2015 <= int(year_str) <= 2035:
                                print(f"    📅 Extracted statement year from closing balance: {year_str}")
                                return year_str
                        
                        # PRIORITY 5: any "to <Month> <day>, <year>"
                        m = re.search(r'to\s*\w+\s*\d+,\s*(\d{4})', text, re.IGNORECASE)
                        if m:
                            year_str = m.group(1)
                            if 2015 <= int(year_str) <= 2035:
                                print(f"    📅 Extracted statement year from 'to' pattern: {year_str}")
                                return year_str
                        
                        # Fallback: month + year anywhere on page (bounded range)
                        m = re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b[^\n,]*\b(\d{4})\b', text, re.IGNORECASE)
                        if m and 2015 <= int(m.group(2)) <= 2035:
                            year_str = m.group(2)
                            print(f"    📅 Extracted statement year from month pattern: {year_str}")
                            return year_str
        except Exception as e:
            print(f"Warning: Could not extract statement year: {e}")
        
        print(f"    ⚠️  Could not extract statement year, defaulting to 2023")
        return '2023'  # Default fallback
    
    def _extract_statement_year_scotiabank(self):
        """Extract statement year from Scotiabank PDF - SCOTIABANK SPECIFIC"""
        try:
            import camelot
            tables = camelot.read_pdf(self.pdf_path, pages="1", flavor="stream")
            
            if tables and len(tables) > 0:
                table1 = tables[0].df.copy().fillna('')
                
                # Find the row with "From:" and "To:" - check row 7 (header) and row 8 (data)
                # "To:" is usually in row 7, dates are in row 8
                for idx in range(min(10, len(table1))):
                    row = table1.iloc[idx]
                    row_list = [str(cell).replace('\n', ' ').strip() for cell in row.tolist()]
                    row_text = ' '.join(row_list)
                    
                    # Priority 1: Check if this row has "To:" - then check next row for dates
                    if 'To:' in row_text and idx + 1 < len(table1):
                        next_row = table1.iloc[idx + 1]
                        next_row_list = [str(cell).replace('\n', ' ').strip() for cell in next_row.tolist()]
                        next_row_text = ' '.join(next_row_list)
                        
                        # Find all dates in the next row (the "To:" date is the last one)
                        all_dates = re.findall(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+(\d{4})\b', next_row_text, re.IGNORECASE)
                        if all_dates:
                            year = all_dates[-1][1]  # Last date's year (the "To:" date)
                            if 2015 <= int(year) <= 2035:
                                print(f"    📅 Extracted statement year from 'To:' date: {year}")
                                return year
                    
                    # Priority 2: Check if this row has date information
                    date_matches = [re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+(\d{4})\b', cell, re.IGNORECASE) for cell in row_list]
                    if any(date_matches):
                        all_years = []
                        for match in date_matches:
                            if match:
                                year = match.group(2)
                                if 2015 <= int(year) <= 2035:
                                    all_years.append(year)
                        
                        if all_years:
                            # If multiple years, prefer the later one (statement period end)
                            statement_year = max(all_years)
                            print(f"    📅 Extracted statement year from dates (preferred latest): {statement_year}")
                            return statement_year
                        
                        # Last fallback: extract any 4-digit year (prefer later year)
                        year_matches = re.findall(r'\b(\d{4})\b', row_text)
                        if year_matches:
                            valid_years = [y for y in year_matches if 2015 <= int(y) <= 2035]
                            if valid_years:
                                statement_year = max(valid_years)
                                print(f"    📅 Extracted statement year (fallback): {statement_year}")
                                return statement_year
        except Exception as e:
            print(f"Warning: Could not extract Scotiabank statement year: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"    ⚠️  Could not extract Scotiabank statement year, defaulting to 2023")
        return '2023'  # Default fallback
    
    def _detect_credit_card_statement(self, text):
        """Detect if this is a credit card statement - SCOTIA VISA SPECIFIC"""
        text_lower = text.lower()
        
        # Check for Scotia Visa credit card indicators
        if 'scotiabank' in text_lower or 'scotia' in text_lower:
            if 'visa' in text_lower and ('credit card' in text_lower or 'statement' in text_lower):
                # Additional check: look for credit card-specific terms
                if 'previous balance' in text_lower or 'new balance' in text_lower or 'account balance' in text_lower:
                    return True
                # Check for credit card statement structure
                if 'ref.#' in text_lower and 'amount($)' in text_lower:
                    return True
        
        return False
    
    def _extract_statement_year_scotia_visa(self):
        """Extract statement year from Scotia Visa credit card statement - SCOTIA VISA SPECIFIC"""
        try:
            import camelot
            tables = camelot.read_pdf(self.pdf_path, pages="1", flavor="stream")
            
            if tables and len(tables) > 0:
                table1 = tables[0].df.fillna('')
                
                # Look for statement period: "Dec 3, 2024 - Jan 2, 2025" or "Statement Period Dec 3, 2024 - Jan 2, 2025"
                # Check all rows in the table
                for idx in range(len(table1)):
                    row = table1.iloc[idx]
                    row_list = [str(cell).replace('\n', ' ').replace('\r', ' ') for cell in row.tolist()]
                    row_text = ' '.join(row_list)
                    
                    # Try multiple patterns
                    # Pattern 1: "Dec 3, 2024 - Jan 2, 2025" (with or without newlines)
                    period_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})\s+-\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})', row_text, re.IGNORECASE)
                    if period_match:
                        statement_period = period_match.group(0)
                        statement_start_year = period_match.group(2)
                        statement_end_year = period_match.group(4)
                        
                        # Store both years for year transition handling
                        self.metadata['statement_start_year'] = statement_start_year
                        self.metadata['statement_end_year'] = statement_end_year
                        self.metadata['statement_period'] = statement_period
                        
                        print(f"    Extracted Scotia Visa statement period: {statement_period}")
                        print(f"    Start year: {statement_start_year}, End year: {statement_end_year}")
                        
                        # Return the end year (for statements that span years)
                        return statement_end_year
                    
                    # Pattern 2: Check each cell individually (sometimes period is in one cell)
                    for cell in row_list:
                        cell_clean = str(cell).replace('\n', ' ').replace('\r', ' ')
                        # Look for the full pattern in individual cells
                        period_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})\s+-\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})', cell_clean, re.IGNORECASE)
                        if period_match:
                            statement_period = period_match.group(0)
                            statement_start_year = period_match.group(2)
                            statement_end_year = period_match.group(4)
                            
                            self.metadata['statement_start_year'] = statement_start_year
                            self.metadata['statement_end_year'] = statement_end_year
                            self.metadata['statement_period'] = statement_period
                            
                            print(f"    Extracted Scotia Visa statement period: {statement_period}")
                            print(f"    Start year: {statement_start_year}, End year: {statement_end_year}")
                            
                            return statement_end_year
        except Exception as e:
            print(f"Warning: Could not extract Scotia Visa statement year: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"    Warning: Could not extract Scotia Visa statement year, defaulting to 2024")
        # Set defaults
        self.metadata['statement_start_year'] = '2024'
        self.metadata['statement_end_year'] = '2024'
        return '2024'  # Default fallback
    
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
        year = str(self.metadata.get('statement_year', '2023'))  # Ensure string
        
        # Try RBC format: "11 Dec"
        match = re.match(r'(\d{1,2})\s+([A-Za-z]{3})', date_str)
        if match:
            day = match.group(1)
            month_abbr = match.group(2)
            month_num = month_map.get(month_abbr, '01')
            # Always use the extracted statement year as-is; do not shift December to prior year
            return f"{year}-{month_num}-{day.zfill(2)}"
        
        # Try BMO/CIBC format: "Jan 04"
        match = re.match(r'([A-Za-z]{3})\s+(\d{1,2})', date_str)
        if match:
            month_abbr = match.group(1)
            day = match.group(2)
            month_num = month_map.get(month_abbr, '01')
            
            # Use year from metadata
            return f"{year}-{month_num}-{day.zfill(2)}"
        
        # Try numeric formats and normalize to YYYY-MM-DD
        # Supports MM/DD/YY, MM/DD/YYYY, YYYY/MM/DD
        try:
            if '/' in date_str or '-' in date_str:
                dt = date_parser.parse(date_str, default=datetime(int(year), 1, 1))
                return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
        
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

