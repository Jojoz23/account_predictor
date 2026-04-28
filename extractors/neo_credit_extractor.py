#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Neo Credit Card extractor."""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_neo_credit_complete import extract_neo_credit_statement
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe


class NeoCreditExtractor(BankExtractorInterface):
    """Extractor for Neo credit card statements."""

    def detect_bank(self, pdf_path: str) -> bool:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages[:2]:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"

            text_lower = text.lower()
            has_neo = "neo financial" in text_lower or "neofinancial.com" in text_lower
            has_card = "mastercard" in text_lower or "payment account summary" in text_lower
            has_statement = "transactions" in text_lower and "new amount owing" in text_lower
            return has_neo and has_card and has_statement
        except Exception:
            return False

    def extract(self, pdf_path: str) -> ExtractionResult:
        try:
            df, opening_balance, closing_balance, statement_year = extract_neo_credit_statement(pdf_path)
            standardized_df = standardize_dataframe(df, is_credit_card=True)

            metadata = {
                "bank": "Neo Financial",
                "is_credit_card": True,
                "opening_balance": opening_balance,
                "closing_balance": closing_balance,
                "statement_year": statement_year,
                "transaction_count": len(standardized_df),
                "extraction_method": "camelot",
            }

            return ExtractionResult(
                df=standardized_df,
                metadata=metadata,
                success=True,
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={"bank": "Neo Financial", "is_credit_card": True},
                success=False,
                error=str(e),
            )
