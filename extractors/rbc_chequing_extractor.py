#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBC Chequing Account Statement Extractor
Standardized extractor for RBC Chequing statements
"""

import sys
import os
import pandas as pd

# Add parent directory to path to import the original script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_rbc_chequing_complete import extract_rbc_chequing_statement
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class RBCChequingExtractor(BankExtractorInterface):
    """Extractor for RBC Chequing account statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """
        Detect if this PDF is an RBC Chequing statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if this appears to be an RBC Chequing statement
        """
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                # Check first page for RBC indicators
                first_page_text = pdf.pages[0].extract_text()
                if not first_page_text:
                    return False
                
                first_page_text_lower = first_page_text.lower()
                
                # Exclude other banks' statements (e.g. TD statement that mentions "RBC VISA" in a transaction)
                if 'toronto-dominion' in first_page_text_lower or 'td bank' in first_page_text_lower:
                    return False
                
                # Check for RBC indicators
                has_rbc = 'royal bank' in first_page_text_lower or 'rbc' in first_page_text_lower
                has_chequing = 'chequing' in first_page_text_lower or 'business account' in first_page_text_lower
                has_account_activity = 'account activity' in first_page_text_lower
                
                # Check for transaction table headers
                has_transaction_headers = (
                    'date' in first_page_text_lower and 
                    ('description' in first_page_text_lower or 'debits' in first_page_text_lower) and
                    ('balance' in first_page_text_lower or 'credits' in first_page_text_lower)
                )
                
                # RBC Chequing statements typically have all of these
                # Make sure it's not a credit card statement
                is_not_credit_card = 'credit card' not in first_page_text_lower and 'mastercard' not in first_page_text_lower
                
                return has_rbc and (has_chequing or has_account_activity) and has_transaction_headers and is_not_credit_card
                
        except Exception:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract transactions from RBC Chequing statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ExtractionResult with transactions and metadata
        """
        try:
            df, opening_balance, closing_balance, statement_year = extract_rbc_chequing_statement(pdf_path)
            
            if df is None or len(df) == 0:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'RBC Chequing'},
                    success=False,
                    error='No transactions extracted'
                )
            
            # Standardize the dataframe (not a credit card)
            standardized_df = standardize_dataframe(df, is_credit_card=False)
            
            # Build metadata
            metadata = {
                'bank': 'RBC Chequing',
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
                metadata={'bank': 'RBC Chequing'},
                success=False,
                error=str(e)
            )
