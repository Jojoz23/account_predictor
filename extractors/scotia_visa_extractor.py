"""Scotia Visa Extractor Implementation"""

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


def extract_scotia_visa_statement(pdf_path: str):
    """
    Extract Scotia Visa (and Scotia AMEX / personal credit card) statements.
    Uses the standalone extract_scotiabank_visa_passport script (all tables,
    REF.#/DATE/DETAILS/AMOUNT, payment sign handling).
    Returns:
    - df: DataFrame with Date, Description, Amount, Running_Balance
    - opening_balance: float or None
    - closing_balance: float or None
    - statement_year: str or None
    """
    from extract_scotiabank_visa_passport import extract_scotiabank_visa_passport

    df, opening_balance, closing_balance, statement_year = extract_scotiabank_visa_passport(str(pdf_path))
    # Return statement_year as str for compatibility with callers
    year_str = str(statement_year) if statement_year is not None else None
    return df, opening_balance, closing_balance, year_str


class ScotiaVisaExtractor(BankExtractorInterface):
    """Extractor for Scotia Visa statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a Scotia card statement (Visa or AMEX). Require REF.# so we don't match bank PDFs that mention 'credit card' in transactions."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() or ""
                text_lower = text.lower()
                has_scotia = 'scotiabank' in text_lower or 'bank of nova scotia' in text_lower
                # Card statements have REF.# in the transaction table; bank statements do not
                has_ref = 'ref.#' in text_lower or 'ref.#' in text
                has_card = 'visa' in text_lower or 'amex' in text_lower or 'american express' in text_lower or 'credit card' in text_lower
                return has_scotia and has_ref and has_card
        except Exception:
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

