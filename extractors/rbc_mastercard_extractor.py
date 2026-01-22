#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBC Mastercard Extractor
Standardized extractor for RBC Mastercard statements
"""

import sys
import os
import pandas as pd

# Add parent directory to path to import the original script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_rbc_mastercard_complete import extract_rbc_mastercard_statement
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class RBCMastercardExtractor(BankExtractorInterface):
    """Extractor for RBC Mastercard statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """
        Detect if this PDF is an RBC Mastercard statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if this appears to be an RBC Mastercard statement
        """
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages[:2]:  # Check first 2 pages
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                # Look for RBC Mastercard indicators
                text_upper = text.upper()
                has_rbc = 'RBC' in text_upper or 'ROYAL BANK' in text_upper
                has_mastercard = 'MASTERCARD' in text_upper
                has_card_number = '****' in text or '**' in text
                
                # Make sure it's not a chequing account
                is_not_chequing = 'CHEQUING' not in text_upper and 'BUSINESS ACCOUNT' not in text_upper
                
                # RBC Mastercard statements typically have all of these
                return has_rbc and has_mastercard and has_card_number and is_not_chequing
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract transactions from RBC Mastercard statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ExtractionResult with transactions and metadata
        """
        try:
            df, opening_balance, closing_balance, statement_year = extract_rbc_mastercard_statement(pdf_path)
            
            if df is None or len(df) == 0:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'RBC Mastercard'},
                    success=False,
                    error='No transactions extracted'
                )
            
            # Standardize the dataframe (credit card format)
            standardized_df = standardize_dataframe(df, is_credit_card=True)
            
            # Build metadata
            metadata = {
                'bank': 'RBC Mastercard',
                'is_credit_card': True,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': statement_year,
                'transaction_count': len(df)
            }
            
            return ExtractionResult(
                df=standardized_df,
                metadata=metadata,
                success=True
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'RBC Mastercard'},
                success=False,
                error=str(e)
            )
