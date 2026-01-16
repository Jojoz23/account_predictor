"""
Bank Extractor Implementations

This package contains individual bank extractor implementations.
Each extractor implements the BankExtractorInterface from standardized_bank_extractors.
"""

from .td_bank_extractor import TDBankExtractor
from .td_visa_extractor import TDVisaExtractor, extract_td_visa_statement
from .scotia_visa_extractor import ScotiaVisaExtractor, extract_scotia_visa_statement
from .scotiabank_extractor import ScotiabankExtractor
from .tangerine_extractor import TangerineExtractor
from .cibc_bank_extractor import CIBCBankExtractor, extract_cibc_bank_statement
from .nb_bank_extractor import NBBankExtractor
from .generic_extractor import GenericExtractor

__all__ = [
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
    'GenericExtractor',
]
