"""TD Bank Extractor Implementation"""

import re

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class TDBankExtractor(BankExtractorInterface):
    """Extractor for TD Bank statements (not TD Visa)"""
    
    def __init__(self):
        # Import TD bank extraction functions
        try:
            # Use the Camelot-first extractor for TD bank statements.
            # This handles table-heavy TD layouts more reliably than the
            # basic pdfplumber table parser.
            from test_td_bank_complete import extract_td_bank_statement_camelot
            self.extract_func = extract_td_bank_statement_camelot
        except ImportError as e:
            raise ImportError(f"Could not import TD bank extraction functions: {e}")
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a TD Bank chequing/savings statement (not Visa)."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ""
                text_lower = text.lower()
                # Remove all whitespace (spaces, newlines, tabs) for robust header matching
                text_nospace = re.sub(r"\s+", "", text_lower)

                # Check for TD Bank indicators (not Visa)
                has_td = (
                    'td bank' in text_lower
                    or 'toronto-dominion' in text_lower
                    or 'tdcanadatrust' in text_nospace
                )

                # Look for common TD deposit account wording
                has_deposit_keywords = (
                    'business chequing account' in text_lower
                    or 'business checking account' in text_lower
                    or 'chequing account' in text_lower
                    or 'chequing acco' in text_lower  # truncated headers
                    or 'businesschequingaccount' in text_nospace
                    or 'chequingaccount' in text_nospace
                )

                # Check if it's actually a Visa STATEMENT (not just mentions "visa" in transactions)
                # Visa statements have specific patterns like "STATEMENT PERIOD", "PREVIOUS STATEMENT BALANCE", etc.
                is_visa_statement = (
                    'statement period' in text_lower
                    and ('visa' in text_lower or 'credit card' in text_lower)
                    and ('previous statement balance' in text_lower or 'previous balance' in text_lower)
                )

                # Also check for TD Visa specific patterns
                has_td_visa_pattern = (
                    (
                        'td business' in text_lower
                        or 'tdbusiness' in text_lower.replace(' ', '')
                        or 'tdvisa' in text_lower.replace(' ', '')
                    )
                    and 'statement period' in text_lower
                )

                # We consider it TD Bank (deposit account) if:
                #  - It clearly looks like TD
                #  - It has deposit-account wording (chequing/savings)
                #  - It does NOT look like a Visa / credit card statement
                return has_td and has_deposit_keywords and not is_visa_statement and not has_td_visa_pattern
        except Exception:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract TD Bank statement"""
        try:
            # Call existing extraction function
            df, opening_balance, closing_balance, statement_year = self.extract_func(pdf_path)
            
            # Standardize DataFrame
            df_standardized = standardize_dataframe(df, is_credit_card=False)
            
            # Create metadata
            metadata = {
                'bank': 'TD',
                'is_credit_card': False,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': str(statement_year) if statement_year else None,
                'extraction_method': 'camelot'
            }
            
            # Update Running_Balance with opening balance if available
            if opening_balance is not None and not df_standardized.empty:
                if 'Withdrawals' in df_standardized.columns and 'Deposits' in df_standardized.columns:
                    df_standardized['Running_Balance'] = opening_balance + (
                        df_standardized['Deposits'].fillna(0) - df_standardized['Withdrawals'].fillna(0)
                    ).cumsum()
            
            return ExtractionResult(
                df=df_standardized,
                metadata=metadata,
                success=True
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'TD', 'is_credit_card': False},
                success=False,
                error=str(e)
            )

