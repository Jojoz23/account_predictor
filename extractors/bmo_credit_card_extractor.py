#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BMO Credit Card Statement Extractor
Standardized extractor for BMO credit card statements
"""

import sys
import os
import pandas as pd

# Add parent directory to path to import the extraction function
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the extraction function
from test_bmo_credit_card_complete import extract_bmo_credit_card_statement
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class BMOCreditCardExtractor(BankExtractorInterface):
    """Extractor for BMO credit card statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """
        Detect if this PDF is a BMO credit card statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if this appears to be a BMO credit card statement
        """
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""
                text_lower = text.lower()
                
                # Must have BMO and credit card indicators
                has_bmo = 'bank of montreal' in text_lower or 'bmo' in text_lower
                has_credit_card = (
                    'credit card' in text_lower or
                    'mastercard' in text_lower or
                    'bmo mastercard' in text_lower or
                    'bmo world elite' in text_lower or
                    ('bank of montreal' in text_lower and ('credit' in text_lower or 'card number' in text_lower))
                )
                
                return has_bmo and has_credit_card
                
        except Exception:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract transactions from BMO credit card statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ExtractionResult with transaction data (same format as original script)
        """
        try:
            df, opening_balance, closing_balance, year = extract_bmo_credit_card_statement(pdf_path)
            
            if df is None or len(df) == 0:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'BMO Credit Card'},
                    success=False,
                    error='No transactions extracted'
                )
            
            # Pass through original data unchanged - same format as extract_bmo_credit_card_statement
            metadata = {
                'bank': 'BMO Credit Card',
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': year,
                'transaction_count': len(df),
                'is_credit_card': True
            }
            
            return ExtractionResult(
                df=df.copy(),
                metadata=metadata,
                success=True
            )
            
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'BMO Credit Card'},
                success=False,
                error=str(e)
            )
    
    def get_name(self) -> str:
        """Return the name of this extractor"""
        return "BMO Credit Card"
