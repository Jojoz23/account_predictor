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
    """Extractor for RBC credit card statements (Mastercard/Visa)"""

    @staticmethod
    def _detect_rbc_card_brand(text: str) -> str:
        """Return RBC card brand from statement text."""
        text_upper = text.upper()
        if 'VISA' in text_upper:
            return 'Visa'
        if 'MASTERCARD' in text_upper:
            return 'Mastercard'
        return 'Card'
    
    def detect_bank(self, pdf_path: str) -> bool:
        """
        Detect if this PDF is an RBC credit card statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if this appears to be an RBC Visa/Mastercard statement
        """
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages[:2]:  # Check first 2 pages
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                # Look for RBC credit-card indicators
                text_upper = text.upper()
                has_rbc = 'RBC' in text_upper or 'ROYAL BANK' in text_upper
                has_card_brand = 'MASTERCARD' in text_upper or 'VISA' in text_upper
                has_card_number = '****' in text or '**' in text
                
                # Make sure it's not a chequing account
                is_not_chequing = 'CHEQUING' not in text_upper and 'BUSINESS ACCOUNT' not in text_upper
                
                # RBC credit-card statements typically have all of these
                return has_rbc and has_card_brand and has_card_number and is_not_chequing
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract transactions from RBC credit-card statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ExtractionResult with transactions and metadata
        """
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                first_page = pdf.pages[0].extract_text() if pdf.pages else ""
            brand = self._detect_rbc_card_brand(first_page or "")
            bank_label = f"RBC {brand}".strip()

            df, opening_balance, closing_balance, statement_year = extract_rbc_mastercard_statement(pdf_path)
            
            if df is None or len(df) == 0:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': bank_label},
                    success=False,
                    error='No transactions extracted'
                )
            
            # Standardize the dataframe (credit card format)
            standardized_df = standardize_dataframe(df, is_credit_card=True)
            
            # Build metadata
            metadata = {
                'bank': bank_label,
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
                metadata={'bank': 'RBC Card'},
                success=False,
                error=str(e)
            )
