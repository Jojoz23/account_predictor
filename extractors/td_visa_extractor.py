"""TD Visa Extractor Implementation"""

import pandas as pd
import re
import camelot
import pdfplumber
from datetime import datetime
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


def extract_td_visa_statement(pdf_path: str):
    """
    Extract TD Visa statement - extracted from test_td_visa_complete.py
    
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
    
    # Step 1: Extract year from statement period
    tables_stream = camelot.read_pdf(pdf_path, pages="1", flavor="stream")
    
    for table_idx, table in enumerate(tables_stream):
        df = table.df.fillna('')
        for idx in range(len(df)):
            row = df.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            
            period_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})\s+to\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})', row_text, re.IGNORECASE)
            if period_match and 'STATEMENT PERIOD' in row_text.upper():
                statement_start_year = period_match.group(2)
                statement_end_year = period_match.group(4)
                break
            elif period_match:
                statement_start_year = period_match.group(2)
                statement_end_year = period_match.group(4)
                break
        if statement_start_year:
            break
    
    if not statement_start_year:
        for table_idx, table in enumerate(tables_stream):
            df = table.df.fillna('')
            for idx in range(min(20, len(df))):
                row_text = ' '.join([str(cell) for cell in df.iloc[idx].tolist()])
                year_match = re.search(r'\b(202[0-9]|203[0-9])\b', row_text)
                if year_match:
                    year = year_match.group(1)
                    statement_start_year = year
                    statement_end_year = year
                    break
            if statement_start_year:
                break
    
    if not statement_start_year:
        statement_start_year = "2024"
        statement_end_year = "2024"
    
    # Step 2: Extract opening and closing balances
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page_num in range(min(3, len(pdf.pages))):
            text += pdf.pages[page_num].extract_text() or ""
    
    opening_patterns = [
        r'PREVIOUS\s+STATEMENT\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Previous\s+Statement\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'Previous\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
    ]
    
    for table_idx, table in enumerate(tables_stream):
        df = table.df.fillna('')
        for idx in range(len(df)):
            row_text = ' '.join([str(cell).upper() for cell in df.iloc[idx].tolist()])
            for pattern in opening_patterns:
                match = re.search(pattern, row_text)
                if match:
                    opening_balance = float(match.group(1).replace(',', ''))
                    break
            if opening_balance:
                break
        if opening_balance:
            break
    
    if not opening_balance:
        for pattern in opening_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                opening_balance = float(match.group(1).replace(',', ''))
                break
    
    closing_patterns = [
        r'TOTAL\s+NEW\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'NEW\s+BALANCE[:\s]+\$?([\d,]+\.?\d{0,2})',
        r'New\s+Balance[:\s]+\$?([\d,]+\.?\d{0,2})',
    ]
    
    tables_stream_balances = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    
    for table_idx, table in enumerate(tables_stream_balances):
        df = table.df.fillna('')
        for idx in range(len(df)):
            row_text = ' '.join([str(cell).upper() for cell in df.iloc[idx].tolist()])
            for pattern in closing_patterns:
                match = re.search(pattern, row_text)
                if match:
                    closing_balance = float(match.group(1).replace(',', ''))
                    break
            if closing_balance:
                break
        if closing_balance:
            break
    
    if not closing_balance:
        for pattern in closing_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                closing_balance = float(match.group(1).replace(',', ''))
                break
    
    # Step 3: Extract transactions
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    tables_stream_all = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    
    for table_idx, table in enumerate(tables_stream_all):
        df = table.df.fillna('')
        
        header_found = False
        date_col = None
        desc_col = None
        amount_col = None
        
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            row_text = ' '.join([str(cell).upper() for cell in row.tolist()])
            
            if 'DATE' in row_text and ('DESCRIPTION' in row_text or 'MERCHANT' in row_text or 'DETAILS' in row_text or 'ACTIVITY' in row_text) and 'AMOUNT' in row_text:
                header_found = True
                
                is_combined_format = False
                for col_idx, cell in enumerate(row):
                    cell_str = str(cell)
                    if '\n' in cell_str and 'DATE' in cell_str.upper() and ('DESCRIPTION' in cell_str.upper() or 'ACTIVITY' in cell_str.upper()):
                        is_combined_format = True
                        date_col = col_idx
                        desc_col = col_idx
                        break
                
                if not is_combined_format:
                    for col_idx, cell in enumerate(row):
                        cell_upper = str(cell).upper()
                        if 'DATE' in cell_upper and date_col is None:
                            date_col = col_idx
                        if ('DESCRIPTION' in cell_upper or 'MERCHANT' in cell_upper or 'DETAILS' in cell_upper or 'ACTIVITY' in cell_upper) and desc_col is None:
                            desc_col = col_idx
                        if 'AMOUNT' in cell_upper and amount_col is None:
                            amount_col = col_idx
                
                if amount_col is None:
                    for col_idx, cell in enumerate(row):
                        cell_upper = str(cell).upper()
                        if 'AMOUNT' in cell_upper:
                            amount_col = col_idx
                            break
                break
        
        if header_found and date_col is not None and desc_col is not None and amount_col is not None:
            start_row = idx + 1
            is_combined_format = (date_col == desc_col)
            
            for row_idx in range(start_row, len(df)):
                row = df.iloc[row_idx]
                
                if is_combined_format:
                    combined_cell = str(row.iloc[date_col]).strip()
                    if not combined_cell or combined_cell == 'nan':
                        continue
                    parts = [p.strip() for p in combined_cell.split('\n') if p.strip()]
                    if len(parts) < 2:
                        continue
                    desc_str = parts[0]
                    date_str = parts[1] if len(parts) > 1 else ''
                else:
                    date_str = str(row.iloc[date_col]).strip()
                    desc_str = str(row.iloc[desc_col]).strip()
                
                amount_str = str(row.iloc[amount_col]).strip()
                
                if not date_str or date_str == 'nan':
                    continue
                
                desc_upper = str(row.iloc[desc_col]).upper() if desc_col is not None and desc_col < len(row) else ''
                date_match_check = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})', date_str, re.IGNORECASE)
                
                if 'PREVIOUS' in desc_upper and 'BALANCE' in desc_upper and not date_match_check:
                    continue
                if 'TOTAL' in desc_upper and 'NEW BALANCE' in desc_upper and not date_match_check:
                    continue
                
                date_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})', date_str, re.IGNORECASE)
                if not date_match:
                    continue
                
                month_name = date_match.group(1).lower()
                day = int(date_match.group(2))
                month = month_map.get(month_name, 1)
                
                if statement_end_year and statement_start_year and statement_start_year != statement_end_year:
                    if month <= 5:
                        year_to_use = int(statement_end_year)
                    else:
                        year_to_use = int(statement_start_year)
                else:
                    year_to_use = int(statement_start_year)
                
                try:
                    full_date = datetime(year_to_use, month, day)
                    date_str_formatted = full_date.strftime('%Y-%m-%d')
                except:
                    continue
                
                amount_clean = amount_str.replace(',', '').replace('$', '').strip()
                is_negative = amount_str.strip().startswith('-') or amount_clean.startswith('-')
                amount_clean = amount_clean.replace('-', '').strip()
                
                amount_match = re.search(r'([\d,]+\.?\d{0,2})', amount_clean)
                if not amount_match:
                    continue
                
                try:
                    amount = float(amount_match.group(1).replace(',', ''))
                    if is_negative:
                        amount = -amount
                except:
                    continue
                
                transactions.append({
                    'Date': date_str_formatted,
                    'Description': desc_str,
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


class TDVisaExtractor(BankExtractorInterface):
    """Extractor for TD Visa statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a TD Visa statement"""
        try:
            # Strong filename hints for TD Visa business statements.
            # This helps when PDF text extraction on page 1 drops key tokens.
            file_name = str(pdf_path).lower().replace(' ', '')
            file_is_td_visa = (
                ('td' in file_name and 'visa' in file_name)
                or 'td_aeroplan_visa_business' in file_name
            )

            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ""
                text_lower = text.lower()
                # Also check without spaces (PDF extraction sometimes removes spaces)
                text_no_spaces = text_lower.replace(' ', '')
                
                # Check for TD indicators (with and without spaces)
                has_td = (
                    'td bank' in text_lower or 
                    'toronto-dominion' in text_lower or 
                    'td canada trust' in text_lower or
                    'tdbusiness' in text_no_spaces or
                    'tdvisa' in text_no_spaces
                )
                
                has_visa = 'visa' in text_lower
                
                # Check for Visa statement indicators (with and without spaces)
                has_visa_statement = (
                    'statement period' in text_lower or 
                    'statementperiod' in text_no_spaces or
                    'credit card' in text_lower or
                    'creditcard' in text_no_spaces or
                    'visa card' in text_lower or
                    'visacard' in text_no_spaces
                )
                
                # Make sure it's not a regular TD bank account (check for account numbers)
                is_bank_account = '5044738' in text or '5047206' in text
                
                # TD Bank statements have "BUSINESS CHEQUING" or "EVERY DAY" account types
                # Visa statements don't have these
                is_bank_statement = (
                    'business chequing' in text_lower or
                    'every day' in text_lower or
                    'cheque/debit' in text_lower or
                    'deposit/credit' in text_lower
                ) and is_bank_account
                
                # Primary detection from content.
                content_is_td_visa = has_td and has_visa and has_visa_statement and not is_bank_statement

                # Fallback: if filename clearly indicates TD Visa and page isn't a TD bank statement.
                return content_is_td_visa or (file_is_td_visa and not is_bank_statement)
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract TD Visa statement"""
        try:
            # Call extraction function
            df, opening_balance, closing_balance, statement_year = extract_td_visa_statement(pdf_path)
            
            # Standardize DataFrame
            df_standardized = standardize_dataframe(df, is_credit_card=True)
            
            # Create metadata
            metadata = {
                'bank': 'TD',
                'is_credit_card': True,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': str(statement_year) if statement_year else None,
                'extraction_method': 'camelot'
            }
            
            # Update Running_Balance with opening balance if available
            if opening_balance is not None and not df_standardized.empty:
                df_standardized['Running_Balance'] = opening_balance + df_standardized['Amount'].cumsum()
            
            return ExtractionResult(
                df=df_standardized,
                metadata=metadata,
                success=True
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'TD', 'is_credit_card': True},
                success=False,
                error=str(e)
            )

