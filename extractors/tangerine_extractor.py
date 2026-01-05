"""Tangerine Bank Extractor Implementation"""

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class TangerineExtractor(BankExtractorInterface):
    """Extractor for Tangerine Bank statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a Tangerine Bank statement"""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ""
                text_lower = text.lower()
                
                # Check for Tangerine indicators
                has_tangerine = (
                    'tangerine' in text_lower or 
                    'ing direct' in text_lower or
                    'tangerine bank' in text_lower
                )
                
                # Check for Tangerine-specific patterns
                has_tangerine_patterns = (
                    'orange key' in text_lower or
                    'www.tangerine.ca' in text_lower or
                    'tangerine.ca' in text_lower
                )
                
                return has_tangerine or has_tangerine_patterns
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract Tangerine Bank statement"""
        try:
            from extract_tangerine_bank import extract_tangerine_bank_statement
            
            # Call extraction function
            df, opening_balance, closing_balance, statement_year = extract_tangerine_bank_statement(pdf_path)
            
            if df is None or df.empty:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'Tangerine', 'is_credit_card': False},
                    success=False,
                    error="No transactions extracted"
                )
            
            # Standardize DataFrame
            df_standardized = standardize_dataframe(df, is_credit_card=False)
            
            # Create metadata
            metadata = {
                'bank': 'Tangerine',
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
                metadata={'bank': 'Tangerine', 'is_credit_card': False},
                success=False,
                error=str(e)
            )

