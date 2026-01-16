"""NB Bank Extractor Implementation (CAD and USD)"""

import re
import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe

# Import extraction function from test script
try:
    from test_nb_complete import extract_nb_statement
except ImportError:
    # Fallback if import fails
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from test_nb_complete import extract_nb_statement


class NBBankExtractor(BankExtractorInterface):
    """Extractor for National Bank (NB) statements (CAD and USD)"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is an NB Bank statement"""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                # Get text from all pages (especially important for disclaimer at bottom)
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
                
                text_lower = full_text.lower()
                
                # Check for NB-specific disclaimer text (most reliable indicator)
                has_nb_disclaimer = 'please check this statement as soon as possible' in text_lower and \
                                   'the bank must be informed in writing of any error or omission within forty-five (45) days' in text_lower
                
                # Check for other NB patterns:
                has_account_statement = 'account statement' in text_lower
                has_period_format = 'period from' in text_lower and re.search(r'\d{4}-\d{2}-\d{2}', text_lower)
                has_account_no_format = 'account no.' in text_lower and 'branch no.' in text_lower
                has_current_account = 'current account' in text_lower and ('cdn$' in text_lower or 'usd$' in text_lower or 'us$' in text_lower)
                
                # Make sure it's not a credit card
                is_not_credit_card = 'credit card' not in text_lower and 'mastercard' not in text_lower
                
                # NB statements have the disclaimer + account statement format
                return (has_nb_disclaimer and has_account_statement and has_period_format and 
                        has_account_no_format and has_current_account and is_not_credit_card)
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract NB Bank statement"""
        try:
            # Call extraction function
            df, opening_balance, closing_balance, statement_year = extract_nb_statement(pdf_path)
            
            # Standardize DataFrame (NB is a bank account, not credit card)
            df_standardized = standardize_dataframe(df, is_credit_card=False)
            
            # Create metadata
            metadata = {
                'bank': 'National Bank',
                'is_credit_card': False,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': str(statement_year) if statement_year else None,
                'extraction_method': 'pdfplumber'
            }
            
            # Update Running_Balance with opening balance if available
            if opening_balance is not None and not df_standardized.empty:
                df_standardized['Running_Balance'] = opening_balance + (df_standardized['Deposits'].fillna(0) - df_standardized['Withdrawals'].fillna(0)).cumsum()
            
            return ExtractionResult(
                df=df_standardized,
                metadata=metadata,
                success=True
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'National Bank', 'is_credit_card': False},
                success=False,
                error=str(e)
            )
