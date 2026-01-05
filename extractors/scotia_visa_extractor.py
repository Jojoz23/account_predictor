"""Scotia Visa Extractor Implementation"""

import pandas as pd
import re
import camelot
from datetime import datetime
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


def extract_scotia_visa_statement(pdf_path: str):
    """
    Extract Scotia Visa statement - extracted from test_scotia_visa_complete.py
    
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
    
    if len(tables_stream) > 0:
        table1 = tables_stream[0].df.fillna('')
        for idx in range(min(10, len(table1))):
            row = table1.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            
            period_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})\s+-\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+(\d{4})', row_text, re.IGNORECASE)
            if period_match:
                statement_start_year = period_match.group(2)
                statement_end_year = period_match.group(4)
                break
    
    if not statement_start_year:
        statement_start_year = "2024"
        statement_end_year = "2024"
    
    # Step 2: Extract opening and closing balances
    all_tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    
    for table_idx, table in enumerate(all_tables):
        df = table.df.fillna('')
        
        for idx in range(len(df)):
            row = df.iloc[idx]
            row_text = ' '.join([str(cell) for cell in row.tolist()])
            row_text_upper = row_text.upper()
            
            if 'PREVIOUS BALANCE' in row_text_upper and opening_balance is None:
                amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                if amount_match:
                    try:
                        opening_balance = float(amount_match.group(1).replace(',', ''))
                    except:
                        pass
            
            if ('NEW BALANCE' in row_text_upper or 'ACCOUNT BALANCE' in row_text_upper) and closing_balance is None:
                amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                if amount_match:
                    try:
                        closing_balance = float(amount_match.group(1).replace(',', ''))
                    except:
                        pass
    
    # Step 3: Extract transactions
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # Find transaction tables (Tables 2 and 6, indices 1 and 5)
    transaction_table_indices = [1, 5]
    
    for table_idx in transaction_table_indices:
        if table_idx >= len(all_tables):
            continue
        
        table = all_tables[table_idx]
        df = table.df.fillna('')
        
        # Find header row
        header_row_idx = None
        for idx in range(min(5, len(df))):
            row = df.iloc[idx]
            row_list = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
            row_text = ' '.join(row_list).upper()
            
            if 'REF.#' in row_text and 'AMOUNT' in row_text:
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            continue
        
        # Process transaction rows
        check_row = header_row_idx + 1
        if check_row < len(df):
            check_row_text = ' '.join([str(cell) for cell in df.iloc[check_row].tolist()]).upper()
            has_ref_pattern = re.match(r'^\d{3}', str(df.iloc[check_row].iloc[0]).strip())
            start_row = check_row if has_ref_pattern else check_row + 1
        else:
            start_row = check_row
        
        for idx in range(start_row, len(df)):
            row = df.iloc[idx]
            row_list = [str(cell).replace('\n', ' ').replace('\r', ' ').strip() for cell in row.tolist()]
            
            if not any(row_list):
                continue
            
            row_text = ' '.join(row_list).upper()
            if 'SUB-TOTAL' in row_text or 'TOTAL' in row_text:
                continue
            
            if len(row_list) < 5:
                continue
            
            ref_str = row_list[0]
            trans_date_str = row_list[1]
            post_date_str = row_list[2]
            description = row_list[3]
            amount_str = row_list[4]
            
            if not re.match(r'^\d{3}$', ref_str):
                continue
            
            # Parse date (use POST DATE)
            date_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', post_date_str, re.IGNORECASE)
            if not date_match:
                continue
            
            month_name = date_match.group(1).lower()
            day = int(date_match.group(2))
            month = month_map.get(month_name, 1)
            
            # Determine year
            if statement_end_year and statement_start_year != statement_end_year:
                if month <= 5:
                    year_to_use = int(statement_end_year)
                else:
                    year_to_use = int(statement_start_year)
            else:
                year_to_use = int(statement_start_year)
            
            try:
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


class ScotiaVisaExtractor(BankExtractorInterface):
    """Extractor for Scotia Visa statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a Scotia Visa statement"""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ""
                text_lower = text.lower()
                
                # Check for Scotia Visa indicators
                has_scotia = 'scotiabank' in text_lower or 'bank of nova scotia' in text_lower
                has_visa = 'visa' in text_lower
                # Check for credit card statement indicators
                has_credit_card = 'credit card' in text_lower or 'visa card' in text_lower or 'ref.#' in text_lower
                
                # Make sure it's not a regular Scotiabank account
                # Scotia Visa statements typically have "REF.#" in transaction tables
                is_visa_statement = has_credit_card or 'ref.#' in text_lower
                
                return has_scotia and has_visa and is_visa_statement
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract Scotia Visa statement"""
        try:
            # Call extraction function
            df, opening_balance, closing_balance, statement_year = extract_scotia_visa_statement(pdf_path)
            
            # Standardize DataFrame
            df_standardized = standardize_dataframe(df, is_credit_card=True)
            
            # Create metadata
            metadata = {
                'bank': 'Scotiabank',
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
                metadata={'bank': 'Scotiabank', 'is_credit_card': True},
                success=False,
                error=str(e)
            )

