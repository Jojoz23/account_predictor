#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AMEX Credit Card Statement Extractor (Amex Bank of Canada / Platinum Card).
Uses Camelot only for table extraction.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_amex_complete import extract_amex_statement
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult


class AMEXExtractor(BankExtractorInterface):
    """Extractor for Amex Bank of Canada Platinum Card statements (Camelot only)."""

    def detect_bank(self, pdf_path: str) -> bool:
        """Return True if PDF appears to be Amex Bank of Canada / Platinum Card statement."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = (pdf.pages[0].extract_text() or "").lower()
            return (
                "amex bank of canada" in text
                or ("american express" in text and "platinum" in text)
                or "the platinum card" in text
            )
        except Exception:
            return False

    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract using Camelot-only extraction."""
        try:
            df, opening_balance, closing_balance, statement_year = extract_amex_statement(pdf_path)

            if df is None or len(df) == 0:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={"bank": "AMEX"},
                    success=False,
                    error="No transactions extracted",
                )

            metadata = {
                "bank": "AMEX",
                "opening_balance": opening_balance,
                "closing_balance": closing_balance,
                "statement_year": statement_year,
                "transaction_count": len(df),
                "is_credit_card": True,
            }

            return ExtractionResult(
                df=df.copy(),
                metadata=metadata,
                success=True,
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={"bank": "AMEX"},
                success=False,
                error=str(e),
            )

    def get_name(self) -> str:
        return "AMEX"
