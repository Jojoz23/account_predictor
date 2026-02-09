#!/usr/bin/env python3
"""
Complete analysis script for CIBC USD Account Statement extraction
Analyzes structure, extracts transactions, and verifies data
"""

import sys
from pathlib import Path

# Import the CAD version's extraction function (they use the same format)
from test_cibc_cad_complete import extract_cibc_cad_statement

def extract_cibc_usd_statement(pdf_path):
    """Complete analysis of CIBC USD statement - uses same logic as CAD"""
    # USD format is identical to CAD format, just different currency
    # So we can reuse the CAD extraction logic
    return extract_cibc_cad_statement(pdf_path)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default to first USD PDF
        pdf_dir = Path("data/Account Statements USD - CIBC 1014")
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        if pdf_files:
            pdf_path = pdf_files[0]
        else:
            print("No PDF files found!")
            sys.exit(1)
    
    result = extract_cibc_usd_statement(pdf_path)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
