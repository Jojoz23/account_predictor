"""Meridian Bank Extractor Implementation (Camelot-first)."""

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe
from test_meridian_bank_complete import extract_meridian_bank_statement


class MeridianBankExtractor(BankExtractorInterface):
    """Extractor for Meridian chequing statements."""

    def detect_bank(self, pdf_path: str) -> bool:
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                text = (pdf.pages[0].extract_text() if pdf.pages else "") or ""
            t = text.lower()
            has_meridian = "meridian" in t or "meridiancu.ca" in t
            has_deposit_accounts = "deposit accounts" in t or "chequing" in t
            is_not_visa = "visa" not in t and "mastercard" not in t and "credit card" not in t
            return has_meridian and has_deposit_accounts and is_not_visa
        except Exception:
            return False

    def extract(self, pdf_path: str) -> ExtractionResult:
        try:
            df, opening_balance, closing_balance, statement_year = extract_meridian_bank_statement(pdf_path)
            if df is None or df.empty:
                return ExtractionResult(
                    df=pd.DataFrame(),
                    metadata={"bank": "Meridian", "is_credit_card": False},
                    success=False,
                    error="No transactions extracted",
                )

            df_std = standardize_dataframe(df, is_credit_card=False)
            if opening_balance is not None and not df_std.empty:
                df_std["Running_Balance"] = opening_balance + (
                    df_std["Deposits"].fillna(0) - df_std["Withdrawals"].fillna(0)
                ).cumsum()

            meta = {
                "bank": "Meridian",
                "is_credit_card": False,
                "opening_balance": opening_balance,
                "closing_balance": closing_balance,
                "statement_year": str(statement_year) if statement_year else None,
                "extraction_method": "camelot",
            }
            return ExtractionResult(df=df_std, metadata=meta, success=True)
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={"bank": "Meridian", "is_credit_card": False},
                success=False,
                error=str(e),
            )

