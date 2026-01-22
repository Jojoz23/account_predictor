#!/usr/bin/env python3
"""
Standardized Bank Statement Extractors Interface

This module provides a standardized interface to all bank-specific extraction scripts.
It wraps existing extraction functions and standardizes their output format.

Design:
- Each bank has its own extractor class that wraps existing extraction logic
- All extractors return the same standardized format
- Easy to add new bank extractors in the future
- Does not modify existing extraction scripts (they remain as-is)
"""

import pandas as pd
from typing import Dict, Optional, Tuple, Any
from pathlib import Path
import sys
import io


# ============================================================================
# STANDARDIZED OUTPUT FORMAT
# ============================================================================

class ExtractionResult:
    """Standardized result format for all bank extractors"""
    
    def __init__(
        self,
        df: pd.DataFrame,
        metadata: Dict[str, Any],
        success: bool = True,
        error: Optional[str] = None
    ):
        """
        Parameters:
        - df: DataFrame with standardized columns
        - metadata: Dict with bank, opening_balance, closing_balance, etc.
        - success: Whether extraction was successful
        - error: Error message if extraction failed
        """
        self.df = df
        self.metadata = metadata
        self.success = success
        self.error = error
    
    def __repr__(self):
        if self.success:
            return f"ExtractionResult(success=True, transactions={len(self.df)}, bank={self.metadata.get('bank')})"
        else:
            return f"ExtractionResult(success=False, error={self.error})"


def standardize_dataframe(df: pd.DataFrame, is_credit_card: bool = False) -> pd.DataFrame:
    """
    Standardize DataFrame columns to consistent format.
    
    Standard format for bank accounts:
    - Date, Description, Withdrawals, Deposits, Balance, Running_Balance
    
    Standard format for credit cards:
    - Date, Description, Amount, Running_Balance
    
    Returns standardized DataFrame with all required columns.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    
    if is_credit_card:
        # Credit card format: Date, Description, Amount, Running_Balance
        required_cols = ['Date', 'Description', 'Amount', 'Running_Balance']
        
        # Ensure Amount column exists
        if 'Amount' not in df.columns:
            # Try to create from Withdrawals/Deposits if they exist
            if 'Withdrawals' in df.columns and 'Deposits' in df.columns:
                df['Amount'] = df['Deposits'].fillna(0) - df['Withdrawals'].fillna(0)
            else:
                df['Amount'] = 0
        
        # Remove Withdrawals/Deposits if they exist (not needed for credit cards)
        if 'Withdrawals' in df.columns:
            df = df.drop(columns=['Withdrawals'])
        if 'Deposits' in df.columns:
            df = df.drop(columns=['Deposits'])
        if 'Balance' in df.columns:
            df = df.drop(columns=['Balance'])
    else:
        # Bank account format: Date, Description, Withdrawals, Deposits, Balance, Running_Balance
        required_cols = ['Date', 'Description', 'Withdrawals', 'Deposits', 'Balance', 'Running_Balance']
        
        # Ensure Withdrawals and Deposits exist
        if 'Withdrawals' not in df.columns:
            df['Withdrawals'] = 0
        if 'Deposits' not in df.columns:
            df['Deposits'] = 0
        
        # If Amount exists but not Withdrawals/Deposits, split it
        if 'Amount' in df.columns and ('Withdrawals' not in df.columns or 'Deposits' not in df.columns):
            df['Withdrawals'] = df.apply(lambda row: abs(row['Amount']) if row['Amount'] < 0 else 0, axis=1)
            df['Deposits'] = df.apply(lambda row: row['Amount'] if row['Amount'] > 0 else 0, axis=1)
    
    # Ensure Date is datetime
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    # Ensure Description exists
    if 'Description' not in df.columns:
        df['Description'] = ''
    
    # Ensure Running_Balance exists (calculate if missing)
    if 'Running_Balance' not in df.columns:
        if is_credit_card and 'Amount' in df.columns:
            # For credit cards, calculate from Amount
            opening = 0  # Will be set from metadata
            df['Running_Balance'] = opening + df['Amount'].cumsum()
        elif not is_credit_card and 'Withdrawals' in df.columns and 'Deposits' in df.columns:
            # For bank accounts, calculate from Deposits - Withdrawals
            opening = 0  # Will be set from metadata
            df['Running_Balance'] = opening + (df['Deposits'].fillna(0) - df['Withdrawals'].fillna(0)).cumsum()
        else:
            df['Running_Balance'] = 0
    
    # Select only required columns (keep any additional columns that might be useful)
    cols_to_keep = required_cols + [col for col in df.columns if col not in required_cols]
    df = df[[col for col in cols_to_keep if col in df.columns]]
    
    return df


# ============================================================================
# BASE EXTRACTOR INTERFACE
# ============================================================================

class BankExtractorInterface:
    """Base interface that all bank extractors must implement"""
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract transactions from PDF.
        
        Returns:
        - ExtractionResult with standardized format
        """
        raise NotImplementedError("Subclasses must implement extract()")
    
    def detect_bank(self, pdf_path: str) -> bool:
        """
        Check if this extractor can handle the given PDF.
        
        Returns:
        - True if this extractor should handle the PDF
        """
        raise NotImplementedError("Subclasses must implement detect_bank()")


# ============================================================================
# BANK EXTRACTORS
# ============================================================================
# Import all extractors from the extractors package

from extractors import (
    TDBankExtractor,
    TDVisaExtractor,
    extract_td_visa_statement,
    ScotiaVisaExtractor,
    extract_scotia_visa_statement,
    ScotiabankExtractor,
    TangerineExtractor,
    CIBCBankExtractor,
    extract_cibc_bank_statement,
    NBBankExtractor,
    NBCompanyCCExtractor,
    GenericExtractor,
)

# Re-export for backward compatibility
__all__ = [
    'ExtractionResult',
    'standardize_dataframe',
    'BankExtractorInterface',
    'TDBankExtractor',
    'TDVisaExtractor',
    'extract_td_visa_statement',
    'ScotiaVisaExtractor',
    'extract_scotia_visa_statement',
    'ScotiabankExtractor',
    'TangerineExtractor',
    'CIBCBankExtractor',
    'extract_cibc_bank_statement',
    'NBBankExtractor',
    'NBCompanyCCExtractor',
    'GenericExtractor',
    'BankExtractorOrchestrator',
    'extract_bank_statement',
]



# ============================================================================
# EXTRACTOR ORCHESTRATOR
# ============================================================================

class BankExtractorOrchestrator:
    """
    Main orchestrator that routes PDFs to appropriate extractors.
    
    Usage:
        orchestrator = BankExtractorOrchestrator()
        result = orchestrator.extract('path/to/statement.pdf')
        
        if result.success:
            df = result.df
            metadata = result.metadata
            print(f"Extracted {len(df)} transactions from {metadata['bank']}")
    """
    
    def __init__(self):
        """Initialize with all available extractors"""
        # Order matters! Check credit cards BEFORE bank accounts
        # because credit card statements might also contain bank name
        from extractors.rbc_chequing_extractor import RBCChequingExtractor
        from extractors.rbc_mastercard_extractor import RBCMastercardExtractor
        
        self.extractors = [
            TDVisaExtractor(),      # Check TD Visa before TD Bank
            ScotiaVisaExtractor(),  # Check Scotia Visa before Scotiabank
            NBCompanyCCExtractor(),  # Check NB Company Credit Card before NB Bank
            RBCMastercardExtractor(), # RBC Mastercard (before RBC Chequing)
            RBCChequingExtractor(), # RBC Chequing (before other RBC products)
            TangerineExtractor(),   # Tangerine Bank (before Scotiabank to avoid false matches)
            TDBankExtractor(),
            ScotiabankExtractor(),
            CIBCBankExtractor(),    # CIBC Bank (CAD and USD)
            NBBankExtractor(),      # National Bank (CAD and USD)
            GenericExtractor()  # Always last (fallback)
        ]
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extract transactions from PDF by routing to appropriate extractor.
        
        Parameters:
        - pdf_path: Path to PDF file
        
        Returns:
        - ExtractionResult with standardized format
        """
        # Try each extractor until one can handle the PDF
        for extractor in self.extractors:
            if extractor.detect_bank(pdf_path):
                print(f"Using {extractor.__class__.__name__} for {Path(pdf_path).name}")
                return extractor.extract(pdf_path)
        
        # Should never reach here (GenericExtractor always returns True)
        return GenericExtractor().extract(pdf_path)
    
    def get_extractor_for_bank(self, bank_name: str) -> Optional[BankExtractorInterface]:
        """Get extractor for a specific bank"""
        bank_lower = bank_name.lower()
        
        if 'td' in bank_lower and 'visa' not in bank_lower:
            return TDBankExtractor()
        elif 'td' in bank_lower and 'visa' in bank_lower:
            return TDVisaExtractor()
        elif 'scotia' in bank_lower and 'visa' in bank_lower:
            return ScotiaVisaExtractor()
        elif 'scotia' in bank_lower:
            return ScotiabankExtractor()
        elif 'tangerine' in bank_lower:
            return TangerineExtractor()
        elif 'cibc' in bank_lower:
            return CIBCBankExtractor()
        elif ('nb' in bank_lower or 'national bank' in bank_lower) and ('company credit card' in bank_lower or 'company cc' in bank_lower):
            return NBCompanyCCExtractor()
        elif 'nb' in bank_lower or 'national bank' in bank_lower:
            return NBBankExtractor()
        elif ('rbc' in bank_lower or 'royal bank' in bank_lower) and ('mastercard' in bank_lower):
            from extractors.rbc_mastercard_extractor import RBCMastercardExtractor
            return RBCMastercardExtractor()
        elif ('rbc' in bank_lower or 'royal bank' in bank_lower) and ('chequing' in bank_lower or 'business account' in bank_lower):
            from extractors.rbc_chequing_extractor import RBCChequingExtractor
            return RBCChequingExtractor()
        else:
            return GenericExtractor()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def extract_bank_statement(pdf_path: str) -> ExtractionResult:
    """
    Convenience function to extract bank statement.
    
    Usage:
        result = extract_bank_statement('path/to/statement.pdf')
        if result.success:
            df = result.df
            print(df.head())
    """
    orchestrator = BankExtractorOrchestrator()
    return orchestrator.extract(pdf_path)


if __name__ == "__main__":
    # Test the interface
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python standardized_bank_extractors.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    print("="*80)
    print("STANDARDIZED BANK EXTRACTOR TEST")
    print("="*80)
    print(f"\nPDF: {pdf_path}\n")
    
    result = extract_bank_statement(pdf_path)
    
    if result.success:
        print(f"\n✅ Extraction successful!")
        print(f"   Bank: {result.metadata.get('bank')}")
        print(f"   Credit Card: {result.metadata.get('is_credit_card')}")
        print(f"   Transactions: {len(result.df)}")
        print(f"   Opening Balance: ${result.metadata.get('opening_balance'):,.2f}" if result.metadata.get('opening_balance') else "   Opening Balance: Not found")
        print(f"   Closing Balance: ${result.metadata.get('closing_balance'):,.2f}" if result.metadata.get('closing_balance') else "   Closing Balance: Not found")
        print(f"\n   Columns: {list(result.df.columns)}")
        print(f"\n   First 5 transactions:")
        print(result.df.head(5).to_string())
    else:
        print(f"\n❌ Extraction failed: {result.error}")

