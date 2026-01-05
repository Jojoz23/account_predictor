"""Generic Extractor Implementation (Fallback)"""

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class GenericExtractor(BankExtractorInterface):
    """Generic extractor using main extract_bank_statements.py as fallback"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Always returns True (fallback extractor)"""
        return True
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract using main extract_bank_statements.py"""
        try:
            from extract_bank_statements import BankStatementExtractor
            
            extractor = BankStatementExtractor(pdf_path)
            df = extractor.extract()
            
            if df is None or df.empty:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'Unknown', 'is_credit_card': False},
                    success=False,
                    error="No transactions extracted"
                )
            
            # Determine if credit card
            is_credit_card = extractor.metadata.get('is_credit_card', False)
            
            # Standardize DataFrame
            df_standardized = standardize_dataframe(df, is_credit_card=is_credit_card)
            
            # Get metadata
            metadata = {
                'bank': extractor.metadata.get('bank', 'Unknown'),
                'is_credit_card': is_credit_card,
                'opening_balance': extractor.metadata.get('opening_balance'),
                'closing_balance': extractor.metadata.get('closing_balance'),
                'statement_year': extractor.metadata.get('statement_year'),
                'extraction_method': 'generic'
            }
            
            return ExtractionResult(
                df=df_standardized,
                metadata=metadata,
                success=True
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'Unknown', 'is_credit_card': False},
                success=False,
                error=str(e)
            )

