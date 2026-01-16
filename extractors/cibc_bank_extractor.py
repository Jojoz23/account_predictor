"""CIBC Bank Extractor Implementation"""

import pandas as pd
import pdfplumber
import re
from datetime import datetime
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


def extract_cibc_bank_statement(pdf_path: str):
    """
    Extract transactions from CIBC bank statement (CAD or USD).
    
    Returns:
    - tuple: (df, opening_balance, closing_balance, statement_year, account_number)
    """
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    account_number = None
    
    # Extract full text
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    # Extract statement period and year
    period_match = re.search(r'For\s+(\w+)\s+(\d{1,2})\s+to\s+(\w+)\s+(\d{1,2}),\s+(\d{4})', full_text, re.IGNORECASE)
    if period_match:
        year = int(period_match.group(5))
        statement_year = year
    
    # Extract account number
    account_match = re.search(r'Account number\s+(\d{2}-\d+)', full_text, re.IGNORECASE)
    if account_match:
        account_number = account_match.group(1)
    
    # Extract opening balance
    opening_match = re.search(r'Opening balance on[^$]*\$([\d,]+\.\d{2})', full_text)
    if opening_match:
        try:
            opening_balance = float(opening_match.group(1).replace(',', ''))
        except:
            pass
    
    # Extract closing balance
    closing_match = re.search(r'Closing balance on[^$]*=\s*\$([\d,]+\.\d{2})', full_text)
    if not closing_match:
        closing_match = re.search(r'Closing balance\s+\$([\d,]+\.\d{2})', full_text)
    if closing_match:
        try:
            closing_balance = float(closing_match.group(1).replace(',', ''))
        except:
            pass
    
    # Extract transactions
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    lines = full_text.split('\n')
    
    # Find start of transaction section
    start_idx = -1
    for i, line in enumerate(lines):
        if "Transaction details" in line or (i > 0 and "Date" in lines[i-1] and "Description" in line):
            start_idx = i + 1
            break
    
    if start_idx > 0:
        i = start_idx
        current_date = None
        
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
                    
                    transaction = _parse_cibc_transaction_line(
                        rest, current_date, month_map, statement_year, lines, i, transactions, opening_balance
                    )
                    if transaction:
                        # Include all transactions, including opening balance (matching original script)
                        transactions.append(transaction)
            else:
                # Continuation line (could be description continuation or new transaction on same date)
                if current_date:
                    # Check if line has numbers that look like amounts
                    amount_pattern = r'\b[\d,]+\.\d{2}\b'
                    amounts = re.findall(amount_pattern, line)
                    
                    # Parse as transaction if it has 1+ amounts (matching original script)
                    if amounts and len(amounts) >= 1:
                        # Skip if it looks like a continuation of description (just text)
                        if not re.match(r'^[A-Z\s\-]+$', line) or len(amounts) >= 2:
                            transaction = _parse_cibc_transaction_line(
                                line, current_date, month_map, statement_year, lines, i, transactions, opening_balance
                            )
                            if transaction:
                                # Include all transactions, including exchange rate lines (matching original script)
                                transactions.append(transaction)
            
            i += 1
    
    # Create DataFrame
    if not transactions:
        return pd.DataFrame(), opening_balance, closing_balance, statement_year, account_number
    
    df = pd.DataFrame(transactions)
    
    # Convert Date to datetime if it's not already
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
    
    # Use Balance column directly from PDF as Running_Balance (matching original script)
    # The original script doesn't calculate deposits from balance changes - it just uses Balance from PDF
    if 'Balance' in df.columns:
        df['Running_Balance'] = df['Balance']
    
    return df, opening_balance, closing_balance, statement_year, account_number


def _parse_cibc_transaction_line(line_text, trans_date, month_map, statement_year, all_lines, line_idx, transactions, opening_balance):
    """Parse a single CIBC transaction line"""
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


class CIBCBankExtractor(BankExtractorInterface):
    """Extractor for CIBC Bank statements (CAD and USD)"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a CIBC bank statement (not credit card)"""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ""
                text_lower = text.lower()
                
                # Check for CIBC indicators
                has_cibc = 'cibc' in text_lower or 'canadian imperial' in text_lower
                
                # Check for account statement format (not credit card)
                is_bank_account = (
                    'account statement' in text_lower and
                    'transaction details' in text_lower and
                    ('withdrawals' in text_lower or 'deposits' in text_lower)
                )
                
                # Make sure it's not a credit card
                is_credit_card = (
                    'credit card' in text_lower or
                    'visa' in text_lower and 'statement period' in text_lower
                )
                
                return has_cibc and is_bank_account and not is_credit_card
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract CIBC bank statement"""
        try:
            # Call extraction function
            df, opening_balance, closing_balance, statement_year, account_number = extract_cibc_bank_statement(pdf_path)
            
            if df is None or df.empty:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'CIBC', 'is_credit_card': False},
                    success=False,
                    error="No transactions extracted"
                )
            
            # Standardize DataFrame
            df_standardized = standardize_dataframe(df, is_credit_card=False)
            
            # Create metadata
            metadata = {
                'bank': 'CIBC',
                'is_credit_card': False,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': str(statement_year) if statement_year else None,
                'account_number': account_number,
                'extraction_method': 'text_parsing'
            }
            
            return ExtractionResult(
                df=df_standardized,
                metadata=metadata,
                success=True
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'CIBC', 'is_credit_card': False},
                success=False,
                error=str(e)
            )
