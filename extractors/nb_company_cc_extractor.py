"""NB Company Credit Card Extractor Implementation"""

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe

# Import the extraction function
from test_nb_company_cc_complete import extract_nb_company_cc_statement


class NBCompanyCCExtractor(BankExtractorInterface):
    """Extractor for NB Company Credit Card statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is an NB Company Credit Card statement"""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ""
                text_lower = text.lower()
                
                # Check for NB Company Credit Card specific patterns
                has_account_pattern = '5258' in text and '819000' in text and '341074' in text
                has_company_pattern = 'canada inc' in text_lower or 'company credit card' in text_lower
                has_credit_card_pattern = 'credit limit' in text_lower or 'monthly transactions' in text_lower
                
                # Make sure it's not a bank account statement
                is_not_bank_account = 'account statement' not in text_lower or 'debit ($)' not in text_lower
                
                return has_account_pattern and has_company_pattern and has_credit_card_pattern and is_not_bank_account
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract NB Company Credit Card statement"""
        try:
            # Call extraction function
            df, opening_balance, closing_balance, statement_year = extract_nb_company_cc_statement(pdf_path)
            
            # Standardize DataFrame (credit card format)
            is_credit_card = True
            df_standardized = standardize_dataframe(df, is_credit_card=is_credit_card)
            
            # Create metadata
            metadata = {
                'bank': 'National Bank',
                'is_credit_card': is_credit_card,
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
                metadata={'bank': 'National Bank', 'is_credit_card': True},
                success=False,
                error=str(e)
            )
