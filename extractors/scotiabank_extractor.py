"""Scotiabank Extractor Implementation"""

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class ScotiabankExtractor(BankExtractorInterface):
    """Extractor for Scotiabank statements (not Visa)"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a Scotiabank statement (not Visa)"""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ""
                text_lower = text.lower()
                
                # Check for Scotiabank indicators (not Visa)
                has_scotia = 'scotiabank' in text_lower or 'bank of nova scotia' in text_lower
                has_visa = 'visa' in text_lower and ('credit card' in text_lower or 'visa card' in text_lower)
                
                return has_scotia and not has_visa
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract Scotiabank statement.
        
        Note: Uses the main extract_bank_statements.py as fallback
        since there's no dedicated Scotiabank extraction script.
        """
        try:
            from extract_bank_statements import BankStatementExtractor
            
            extractor = BankStatementExtractor(pdf_path)
            df = extractor.extract(strategy='camelot')
            
            if df is None or df.empty:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'Scotiabank', 'is_credit_card': False},
                    success=False,
                    error="No transactions extracted"
                )
            
            # Standardize DataFrame
            df_standardized = standardize_dataframe(df, is_credit_card=False)
            
            # Get metadata from extractor
            metadata = {
                'bank': extractor.metadata.get('bank', 'Scotiabank'),
                'is_credit_card': extractor.metadata.get('is_credit_card', False),
                'opening_balance': extractor.metadata.get('opening_balance'),
                'closing_balance': extractor.metadata.get('closing_balance'),
                'statement_year': extractor.metadata.get('statement_year'),
                'extraction_method': 'camelot'
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

