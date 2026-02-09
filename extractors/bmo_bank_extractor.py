#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BMO Bank Statement Extractor
Standardized extractor for BMO bank statements
"""

import sys
import os
import pandas as pd

# Add parent directory to path to import the extraction function
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the extraction function
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_bmo_bank_camelot_complete import extract_bmo_bank_statement_camelot as extract_bmo_bank_statement
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult


class BMOBankExtractor(BankExtractorInterface):
    """Extractor for BMO bank statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """
        Detect if this PDF is a BMO bank statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if this appears to be a BMO bank statement
        """
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                # Check first page for BMO indicators
                first_page_text = pdf.pages[0].extract_text()
                if not first_page_text:
                    return False
                
                first_page_text_lower = first_page_text.lower()
                
                # Check for BMO indicators
                has_bmo = 'bank of montreal' in first_page_text_lower or 'bmo' in first_page_text_lower
                has_business_banking = 'business banking' in first_page_text_lower or 'business account' in first_page_text_lower
                
                # Check for transaction table headers
                has_transaction_headers = (
                    'date' in first_page_text_lower and 
                    'description' in first_page_text_lower and
                    ('amountsdebited' in first_page_text_lower or 'amounts credited' in first_page_text_lower) and
                    'balance' in first_page_text_lower
                )
                
                # Make sure it's not a credit card statement
                is_not_credit_card = 'credit card' not in first_page_text_lower
                
                return has_bmo and (has_business_banking or has_transaction_headers) and is_not_credit_card
                
        except Exception:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract transactions from BMO bank statement
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ExtractionResult with transactions and metadata
        """
        try:
            df, opening_balance, closing_balance, statement_year = extract_bmo_bank_statement(pdf_path)
            
            if df is None or len(df) == 0:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={'bank': 'BMO'},
                    success=False,
                    error='No transactions extracted'
                )
            
            # Pass through original data unchanged - same format as extract_bmo_bank_statement_camelot
            metadata = {
                'bank': 'BMO',
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': statement_year,
                'transaction_count': len(df),
                'is_credit_card': False
            }
            
            return ExtractionResult(
                df=df.copy(),
                metadata=metadata,
                success=True
            )
            
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': 'BMO'},
                success=False,
                error=str(e)
            )
