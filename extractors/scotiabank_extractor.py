"""Scotiabank Extractor Implementation"""

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class ScotiabankExtractor(BankExtractorInterface):
    """Extractor for Scotiabank statements (not Visa)"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a Scotiabank bank statement (chequing/savings/business). Exclude card statements (they have REF.#)."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() or ""
                text_lower = text.lower()
                has_scotia = 'scotiabank' in text_lower or 'bank of nova scotia' in text_lower
                # Scotia Business/layout when "scotiabank" not in text: Statement Of, Account Details, Balance ($)
                has_scotia_bank_layout = (
                    'statement of' in text_lower and 'account details' in text_lower
                    and 'balance' in text_lower and ('withdrawal' in text_lower or 'debit' in text_lower)
                )
                is_card_statement = 'ref.#' in text_lower or 'ref.#' in text
                return (has_scotia or has_scotia_bank_layout) and not is_card_statement
        except Exception:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract Scotiabank bank statement (chequing/savings/business).
        Uses the standalone extract_scotiabank_cheq_savings script (all pages/tables,
        BALANCE FORWARD, multiline descriptions, closing balance from last row).
        """
        try:
            from extract_scotiabank_cheq_savings import extract_scotiabank_cheq_savings

            df, opening_balance, closing_balance, statement_year = extract_scotiabank_cheq_savings(str(pdf_path))

            if df is None or df.empty:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'Scotiabank', 'is_credit_card': False},
                    success=False,
                    error="No transactions extracted"
                )

            df_standardized = standardize_dataframe(df, is_credit_card=False)

            metadata = {
                'bank': 'Scotiabank',
                'is_credit_card': False,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': int(statement_year) if statement_year else None,
                'extraction_method': 'extract_scotiabank_cheq_savings'
            }

            return ExtractionResult(
                df=df_standardized,
                metadata=metadata,
                success=True
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'Scotiabank', 'is_credit_card': False},
                success=False,
                error=str(e)
            )

