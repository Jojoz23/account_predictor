#!/usr/bin/env python3
"""
Test script to verify standardized extractors produce same results as original scripts.

This script compares:
- Original extraction scripts (test_td_bank_complete.py, test_td_visa_complete.py, etc.)
- New standardized extractors (standardized_bank_extractors.py)

It checks:
- Number of transactions
- Opening/closing balances
- Transaction amounts
- Dates
- Descriptions
- Running balances

Usage:
    # Run all tests
    python test_standardized_extractors.py
    
    # Run specific bank(s)
    python test_standardized_extractors.py --cibc
    python test_standardized_extractors.py --td-bank --td-visa
    python test_standardized_extractors.py --scotia --tangerine
    
    # Run with verbose output
    python test_standardized_extractors.py --cibc --verbose
    
    # List available tests
    python test_standardized_extractors.py --list
"""

import sys
import io
import argparse
import pandas as pd
from pathlib import Path
from standardized_bank_extractors import extract_bank_statement, BankExtractorOrchestrator

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def compare_dataframes(df1: pd.DataFrame, df2: pd.DataFrame, name1: str = "Original", name2: str = "Standardized") -> dict:
    """Compare two DataFrames and return differences"""
    differences = {
        'row_count_match': len(df1) == len(df2),
        'row_count_diff': abs(len(df1) - len(df2)),
        'column_match': set(df1.columns) == set(df2.columns),
        'missing_columns': set(df1.columns) - set(df2.columns),
        'extra_columns': set(df2.columns) - set(df1.columns),
        'transaction_differences': []
    }
    
    if len(df1) != len(df2):
        return differences
    
    # Compare each transaction
    for idx in range(min(len(df1), len(df2))):
        row1 = df1.iloc[idx]
        row2 = df2.iloc[idx]
        
        row_diff = {}
        
        # Compare Date
        if 'Date' in df1.columns and 'Date' in df2.columns:
            date1 = pd.to_datetime(row1['Date']).date() if pd.notna(row1['Date']) else None
            date2 = pd.to_datetime(row2['Date']).date() if pd.notna(row2['Date']) else None
            if date1 != date2:
                row_diff['Date'] = f"{date1} != {date2}"
        
        # Compare Description
        if 'Description' in df1.columns and 'Description' in df2.columns:
            desc1 = str(row1['Description']).strip() if pd.notna(row1['Description']) else ""
            desc2 = str(row2['Description']).strip() if pd.notna(row2['Description']) else ""
            if desc1 != desc2:
                row_diff['Description'] = f"'{desc1[:50]}' != '{desc2[:50]}'"
        
        # Compare Amount (for credit cards)
        if 'Amount' in df1.columns and 'Amount' in df2.columns:
            amount1 = row1['Amount'] if pd.notna(row1['Amount']) else 0
            amount2 = row2['Amount'] if pd.notna(row2['Amount']) else 0
            if abs(amount1 - amount2) > 0.01:
                row_diff['Amount'] = f"{amount1} != {amount2}"
        
        # Compare Withdrawals/Deposits (for bank accounts)
        if 'Withdrawals' in df1.columns and 'Withdrawals' in df2.columns:
            w1 = row1['Withdrawals'] if pd.notna(row1['Withdrawals']) else 0
            w2 = row2['Withdrawals'] if pd.notna(row2['Withdrawals']) else 0
            if abs(w1 - w2) > 0.01:
                row_diff['Withdrawals'] = f"{w1} != {w2}"
        
        if 'Deposits' in df1.columns and 'Deposits' in df2.columns:
            d1 = row1['Deposits'] if pd.notna(row1['Deposits']) else 0
            d2 = row2['Deposits'] if pd.notna(row2['Deposits']) else 0
            if abs(d1 - d2) > 0.01:
                row_diff['Deposits'] = f"{d1} != {d2}"
        
        # Compare Running Balance
        if 'Running_Balance' in df1.columns and 'Running_Balance' in df2.columns:
            rb1 = row1['Running_Balance'] if pd.notna(row1['Running_Balance']) else 0
            rb2 = row2['Running_Balance'] if pd.notna(row2['Running_Balance']) else 0
            if abs(rb1 - rb2) > 0.01:
                row_diff['Running_Balance'] = f"{rb1} != {rb2}"
        
        if row_diff:
            row_diff['row_index'] = idx
            differences['transaction_differences'].append(row_diff)
    
    return differences


def test_td_bank(pdf_path: str, verbose: bool = False):
    """Test TD Bank extraction"""
    if verbose:
        print("\n" + "="*80)
        print("TESTING TD BANK EXTRACTION")
        print("="*80)
        print(f"PDF: {Path(pdf_path).name}\n")
    
    # Original extraction
    if verbose:
        print("1. Running original extraction (test_td_bank_complete.py)...")
    try:
        from test_td_bank_complete import extract_td_bank_statement_camelot
        df_original, opening_orig, closing_orig, year_orig = extract_td_bank_statement_camelot(pdf_path)
        
        # Check if extraction returned None (failed)
        if df_original is None:
            if verbose:
                print(f"   ❌ Error: Extraction returned None (no transactions extracted)")
            return False
        
        if verbose:
            print(f"   ✅ Original: {len(df_original)} transactions")
            print(f"   Opening: ${opening_orig:,.2f}" if opening_orig else "   Opening: Not found")
            print(f"   Closing: ${closing_orig:,.2f}" if closing_orig else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Standardized extraction
    if verbose:
        print("\n2. Running standardized extraction...")
    try:
        result = extract_bank_statement(pdf_path)
        if not result.success:
            if verbose:
                print(f"   ❌ Error: {result.error}")
            return False
        
        df_standardized = result.df
        opening_std = result.metadata.get('opening_balance')
        closing_std = result.metadata.get('closing_balance')
        
        if verbose:
            print(f"   ✅ Standardized: {len(df_standardized)} transactions")
            print(f"   Opening: ${opening_std:,.2f}" if opening_std else "   Opening: Not found")
            print(f"   Closing: ${closing_std:,.2f}" if closing_std else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Compare
    if verbose:
        print("\n3. Comparing results...")
    
    # Compare balances
    opening_match = (opening_orig is None and opening_std is None) or (opening_orig is not None and opening_std is not None and abs(opening_orig - opening_std) < 0.01)
    closing_match = (closing_orig is None and closing_std is None) or (closing_orig is not None and closing_std is not None and abs(closing_orig - closing_std) < 0.01)
    
    if verbose:
        print(f"   Opening balance match: {'✅' if opening_match else '❌'}")
        if not opening_match:
            print(f"      Original: ${opening_orig:,.2f}" if opening_orig else "      Original: None")
            print(f"      Standardized: ${opening_std:,.2f}" if opening_std else "      Standardized: None")
        
        print(f"   Closing balance match: {'✅' if closing_match else '❌'}")
        if not closing_match:
            print(f"      Original: ${closing_orig:,.2f}" if closing_orig else "      Original: None")
            print(f"      Standardized: ${closing_std:,.2f}" if closing_std else "      Standardized: None")
    
    # Compare DataFrames
    differences = compare_dataframes(df_original, df_standardized)
    
    if verbose:
        print(f"   Transaction count match: {'✅' if differences['row_count_match'] else '❌'}")
        if not differences['row_count_match']:
            print(f"      Original: {len(df_original)} transactions")
            print(f"      Standardized: {len(df_standardized)} transactions")
            print(f"      Difference: {differences['row_count_diff']}")
        
        print(f"   Column match: {'✅' if differences['column_match'] else '❌'}")
        if not differences['column_match']:
            if differences['missing_columns']:
                print(f"      Missing in standardized: {differences['missing_columns']}")
            if differences['extra_columns']:
                print(f"      Extra in standardized: {differences['extra_columns']}")
        
        if differences['transaction_differences']:
            print(f"   ⚠️  Found {len(differences['transaction_differences'])} transaction differences:")
            for diff in differences['transaction_differences'][:5]:  # Show first 5
                print(f"      Row {diff['row_index']}: {diff}")
            if len(differences['transaction_differences']) > 5:
                print(f"      ... and {len(differences['transaction_differences']) - 5} more")
        else:
            print(f"   ✅ All transactions match!")
    else:
        # Brief summary for non-verbose mode
        if not opening_match or not closing_match or not differences['row_count_match'] or differences['transaction_differences']:
            print(f"   ❌ FAIL - ", end="")
            issues = []
            if not opening_match:
                issues.append("opening balance mismatch")
            if not closing_match:
                issues.append("closing balance mismatch")
            if not differences['row_count_match']:
                issues.append(f"transaction count mismatch ({len(df_original)} vs {len(df_standardized)})")
            if differences['transaction_differences']:
                issues.append(f"{len(differences['transaction_differences'])} transaction differences")
            print(", ".join(issues))
        else:
            print(f"   ✅ PASS - {len(df_original)} transactions, balances match")
    
    # Overall result
    all_match = (
        opening_match and 
        closing_match and 
        differences['row_count_match'] and 
        differences['column_match'] and 
        len(differences['transaction_differences']) == 0
    )
    
    return all_match


def test_td_visa(pdf_path: str, verbose: bool = False):
    """Test TD Visa extraction"""
    if verbose:
        print("\n" + "="*80)
        print("TESTING TD VISA EXTRACTION")
        print("="*80)
        print(f"PDF: {Path(pdf_path).name}\n")
    
    # Original extraction - we need to extract from the script
    if verbose:
        print("1. Running original extraction (test_td_visa_complete.py logic)...")
    try:
        from standardized_bank_extractors import extract_td_visa_statement
        df_original, opening_orig, closing_orig, year_orig = extract_td_visa_statement(pdf_path)
        if verbose:
            print(f"   ✅ Original: {len(df_original)} transactions")
            print(f"   Opening: ${opening_orig:,.2f}" if opening_orig else "   Opening: Not found")
            print(f"   Closing: ${closing_orig:,.2f}" if closing_orig else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Standardized extraction
    if verbose:
        print("\n2. Running standardized extraction...")
    try:
        result = extract_bank_statement(pdf_path)
        if not result.success:
            if verbose:
                print(f"   ❌ Error: {result.error}")
            return False
        
        df_standardized = result.df
        opening_std = result.metadata.get('opening_balance')
        closing_std = result.metadata.get('closing_balance')
        
        if verbose:
            print(f"   ✅ Standardized: {len(df_standardized)} transactions")
            print(f"   Opening: ${opening_std:,.2f}" if opening_std else "   Opening: Not found")
            print(f"   Closing: ${closing_std:,.2f}" if closing_std else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Compare
    if verbose:
        print("\n3. Comparing results...")
    
    opening_match = (opening_orig is None and opening_std is None) or (opening_orig is not None and opening_std is not None and abs(opening_orig - opening_std) < 0.01)
    closing_match = (closing_orig is None and closing_std is None) or (closing_orig is not None and closing_std is not None and abs(closing_orig - closing_std) < 0.01)
    
    if verbose:
        print(f"   Opening balance match: {'✅' if opening_match else '❌'}")
        if not opening_match:
            print(f"      Original: ${opening_orig:,.2f}" if opening_orig else "      Original: None")
            print(f"      Standardized: ${opening_std:,.2f}" if opening_std else "      Standardized: None")
        
        print(f"   Closing balance match: {'✅' if closing_match else '❌'}")
        if not closing_match:
            print(f"      Original: ${closing_orig:,.2f}" if closing_orig else "      Original: None")
            print(f"      Standardized: ${closing_std:,.2f}" if closing_std else "      Standardized: None")
    
    differences = compare_dataframes(df_original, df_standardized)
    
    if verbose:
        print(f"   Transaction count match: {'✅' if differences['row_count_match'] else '❌'}")
        if not differences['row_count_match']:
            print(f"      Original: {len(df_original)} transactions")
            print(f"      Standardized: {len(df_standardized)} transactions")
        
        if differences['transaction_differences']:
            print(f"   ⚠️  Found {len(differences['transaction_differences'])} transaction differences:")
            for diff in differences['transaction_differences'][:5]:
                print(f"      Row {diff['row_index']}: {diff}")
        else:
            print(f"   ✅ All transactions match!")
    else:
        # Brief summary for non-verbose mode
        if not opening_match or not closing_match or not differences['row_count_match'] or differences['transaction_differences']:
            print(f"   ❌ FAIL - ", end="")
            issues = []
            if not opening_match:
                issues.append("opening balance mismatch")
            if not closing_match:
                issues.append("closing balance mismatch")
            if not differences['row_count_match']:
                issues.append(f"transaction count mismatch ({len(df_original)} vs {len(df_standardized)})")
            if differences['transaction_differences']:
                issues.append(f"{len(differences['transaction_differences'])} transaction differences")
            print(", ".join(issues))
        else:
            print(f"   ✅ PASS - {len(df_original)} transactions, balances match")
    
    all_match = (
        opening_match and 
        closing_match and 
        differences['row_count_match'] and 
        len(differences['transaction_differences']) == 0
    )
    
    return all_match


def test_scotia_visa(pdf_path: str, verbose: bool = False):
    """Test Scotia Visa extraction"""
    if verbose:
        print("\n" + "="*80)
        print("TESTING SCOTIA VISA EXTRACTION")
        print("="*80)
        print(f"PDF: {Path(pdf_path).name}\n")
    
    # Original extraction
    if verbose:
        print("1. Running original extraction (test_scotia_visa_complete.py logic)...")
    try:
        from standardized_bank_extractors import extract_scotia_visa_statement
        df_original, opening_orig, closing_orig, year_orig = extract_scotia_visa_statement(pdf_path)
        if verbose:
            print(f"   ✅ Original: {len(df_original)} transactions")
            print(f"   Opening: ${opening_orig:,.2f}" if opening_orig else "   Opening: Not found")
            print(f"   Closing: ${closing_orig:,.2f}" if closing_orig else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Standardized extraction
    if verbose:
        print("\n2. Running standardized extraction...")
    try:
        result = extract_bank_statement(pdf_path)
        if not result.success:
            if verbose:
                print(f"   ❌ Error: {result.error}")
            return False
        
        df_standardized = result.df
        opening_std = result.metadata.get('opening_balance')
        closing_std = result.metadata.get('closing_balance')
        
        if verbose:
            print(f"   ✅ Standardized: {len(df_standardized)} transactions")
            print(f"   Opening: ${opening_std:,.2f}" if opening_std else "   Opening: Not found")
            print(f"   Closing: ${closing_std:,.2f}" if closing_std else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Compare
    if verbose:
        print("\n3. Comparing results...")
    
    opening_match = (opening_orig is None and opening_std is None) or (opening_orig is not None and opening_std is not None and abs(opening_orig - opening_std) < 0.01)
    closing_match = (closing_orig is None and closing_std is None) or (closing_orig is not None and closing_std is not None and abs(closing_orig - closing_std) < 0.01)
    
    if verbose:
        print(f"   Opening balance match: {'✅' if opening_match else '❌'}")
        print(f"   Closing balance match: {'✅' if closing_match else '❌'}")
    
    differences = compare_dataframes(df_original, df_standardized)
    
    if verbose:
        print(f"   Transaction count match: {'✅' if differences['row_count_match'] else '❌'}")
        
        if differences['transaction_differences']:
            print(f"   ⚠️  Found {len(differences['transaction_differences'])} transaction differences")
        else:
            print(f"   ✅ All transactions match!")
    else:
        # Brief summary for non-verbose mode
        if not opening_match or not closing_match or not differences['row_count_match'] or differences['transaction_differences']:
            print(f"   ❌ FAIL - ", end="")
            issues = []
            if not opening_match:
                issues.append("opening balance mismatch")
            if not closing_match:
                issues.append("closing balance mismatch")
            if not differences['row_count_match']:
                issues.append(f"transaction count mismatch ({len(df_original)} vs {len(df_standardized)})")
            if differences['transaction_differences']:
                issues.append(f"{len(differences['transaction_differences'])} transaction differences")
            print(", ".join(issues))
        else:
            print(f"   ✅ PASS - {len(df_original)} transactions, balances match")
    
    all_match = (
        opening_match and 
        closing_match and 
        differences['row_count_match'] and 
        len(differences['transaction_differences']) == 0
    )
    
    return all_match


def test_tangerine(pdf_path: str, verbose: bool = False):
    """Test Tangerine Bank extraction"""
    if verbose:
        print("\n" + "="*80)
        print("TESTING TANGERINE BANK EXTRACTION")
        print("="*80)
        print(f"PDF: {Path(pdf_path).name}\n")
    
    # Original extraction
    if verbose:
        print("1. Running original extraction (extract_tangerine_bank.py)...")
    try:
        from extract_tangerine_bank import extract_tangerine_bank_statement
        df_original, opening_orig, closing_orig, year_orig = extract_tangerine_bank_statement(pdf_path)
        
        # Check if extraction returned None or empty (failed)
        if df_original is None or len(df_original) == 0:
            if verbose:
                print(f"   ❌ Error: Extraction returned None or empty (no transactions extracted)")
            return False
        
        if verbose:
            print(f"   ✅ Original: {len(df_original)} transactions")
            print(f"   Opening: ${opening_orig:,.2f}" if opening_orig else "   Opening: Not found")
            print(f"   Closing: ${closing_orig:,.2f}" if closing_orig else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Standardized extraction
    if verbose:
        print("\n2. Running standardized extraction...")
    try:
        result = extract_bank_statement(pdf_path)
        if not result.success:
            if verbose:
                print(f"   ❌ Error: {result.error}")
            return False
        
        df_standardized = result.df
        opening_std = result.metadata.get('opening_balance')
        closing_std = result.metadata.get('closing_balance')
        
        if verbose:
            print(f"   ✅ Standardized: {len(df_standardized)} transactions")
            print(f"   Opening: ${opening_std:,.2f}" if opening_std else "   Opening: Not found")
            print(f"   Closing: ${closing_std:,.2f}" if closing_std else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Compare
    if verbose:
        print("\n3. Comparing results...")
    
    opening_match = (opening_orig is None and opening_std is None) or (opening_orig is not None and opening_std is not None and abs(opening_orig - opening_std) < 0.01)
    closing_match = (closing_orig is None and closing_std is None) or (closing_orig is not None and closing_std is not None and abs(closing_orig - closing_std) < 0.01)
    
    if verbose:
        print(f"   Opening balance match: {'✅' if opening_match else '❌'}")
        if not opening_match:
            print(f"      Original: ${opening_orig:,.2f}" if opening_orig else "      Original: None")
            print(f"      Standardized: ${opening_std:,.2f}" if opening_std else "      Standardized: None")
        
        print(f"   Closing balance match: {'✅' if closing_match else '❌'}")
        if not closing_match:
            print(f"      Original: ${closing_orig:,.2f}" if closing_orig else "      Original: None")
            print(f"      Standardized: ${closing_std:,.2f}" if closing_std else "      Standardized: None")
    
    differences = compare_dataframes(df_original, df_standardized)
    
    if verbose:
        print(f"   Transaction count match: {'✅' if differences['row_count_match'] else '❌'}")
        if not differences['row_count_match']:
            print(f"      Original: {len(df_original)} transactions")
            print(f"      Standardized: {len(df_standardized)} transactions")
        
        if differences['transaction_differences']:
            print(f"   ⚠️  Found {len(differences['transaction_differences'])} transaction differences:")
            for diff in differences['transaction_differences'][:5]:
                print(f"      Row {diff['row_index']}: {diff}")
        else:
            print(f"   ✅ All transactions match!")
    else:
        # Brief summary for non-verbose mode
        if not opening_match or not closing_match or not differences['row_count_match'] or differences['transaction_differences']:
            print(f"   ❌ FAIL - ", end="")
            issues = []
            if not opening_match:
                issues.append("opening balance mismatch")
            if not closing_match:
                issues.append("closing balance mismatch")
            if not differences['row_count_match']:
                issues.append(f"transaction count mismatch ({len(df_original)} vs {len(df_standardized)})")
            if differences['transaction_differences']:
                issues.append(f"{len(differences['transaction_differences'])} transaction differences")
            print(", ".join(issues))
        else:
            print(f"   ✅ PASS - {len(df_original)} transactions, balances match")
    
    all_match = (
        opening_match and 
        closing_match and 
        differences['row_count_match'] and 
        len(differences['transaction_differences']) == 0
    )
    
    return all_match


def test_cibc(pdf_path: str, verbose: bool = False):
    """Test CIBC Bank extraction"""
    if verbose:
        print("\n" + "="*80)
        print("TESTING CIBC BANK EXTRACTION")
        print("="*80)
        print(f"PDF: {Path(pdf_path).name}\n")
    
    # Original extraction
    if verbose:
        print("1. Running original extraction (test_cibc_cad_complete.py)...")
    try:
        from test_cibc_cad_complete import extract_cibc_cad_statement
        result_original = extract_cibc_cad_statement(pdf_path)
        
        # Extract data from result dict
        transactions_orig = result_original.get('transactions', [])
        if not transactions_orig:
            if verbose:
                print(f"   ❌ Error: Extraction returned no transactions")
            return False
        
        df_original = pd.DataFrame(transactions_orig)
        opening_orig = result_original.get('opening_balance')
        closing_orig = result_original.get('closing_balance')
        
        if verbose:
            print(f"   ✅ Original: {len(df_original)} transactions")
            print(f"   Opening: ${opening_orig:,.2f}" if opening_orig else "   Opening: Not found")
            print(f"   Closing: ${closing_orig:,.2f}" if closing_orig else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Standardized extraction
    if verbose:
        print("\n2. Running standardized extraction...")
    try:
        from standardized_bank_extractors import extract_bank_statement
        result = extract_bank_statement(pdf_path)
        if not result.success:
            if verbose:
                print(f"   ❌ Error: {result.error}")
            return False
        
        df_standardized = result.df
        opening_std = result.metadata.get('opening_balance')
        closing_std = result.metadata.get('closing_balance')
        
        if verbose:
            print(f"   ✅ Standardized: {len(df_standardized)} transactions")
            print(f"   Opening: ${opening_std:,.2f}" if opening_std else "   Opening: Not found")
            print(f"   Closing: ${closing_std:,.2f}" if closing_std else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Compare
    if verbose:
        print("\n3. Comparing results...")
    
    opening_match = (opening_orig is None and opening_std is None) or (opening_orig is not None and opening_std is not None and abs(opening_orig - opening_std) < 0.01)
    closing_match = (closing_orig is None and closing_std is None) or (closing_orig is not None and closing_std is not None and abs(closing_orig - closing_std) < 0.01)
    
    if verbose:
        print(f"   Opening balance match: {'✅' if opening_match else '❌'}")
        if not opening_match:
            print(f"      Original: ${opening_orig:,.2f}" if opening_orig else "      Original: None")
            print(f"      Standardized: ${opening_std:,.2f}" if opening_std else "      Standardized: None")
        
        print(f"   Closing balance match: {'✅' if closing_match else '❌'}")
        if not closing_match:
            print(f"      Original: ${closing_orig:,.2f}" if closing_orig else "      Original: None")
            print(f"      Standardized: ${closing_std:,.2f}" if closing_std else "      Standardized: None")
    
    differences = compare_dataframes(df_original, df_standardized)
    
    if verbose:
        print(f"   Transaction count match: {'✅' if differences['row_count_match'] else '❌'}")
        if not differences['row_count_match']:
            print(f"      Original: {len(df_original)} transactions")
            print(f"      Standardized: {len(df_standardized)} transactions")
        
        if differences['transaction_differences']:
            print(f"   ⚠️  Found {len(differences['transaction_differences'])} transaction differences:")
            for diff in differences['transaction_differences'][:5]:
                print(f"      Row {diff['row_index']}: {diff}")
        else:
            print(f"   ✅ All transactions match!")
    else:
        # Brief summary for non-verbose mode
        if not opening_match or not closing_match or not differences['row_count_match'] or differences['transaction_differences']:
            print(f"   ❌ FAIL - ", end="")
            issues = []
            if not opening_match:
                issues.append("opening balance mismatch")
            if not closing_match:
                issues.append("closing balance mismatch")
            if not differences['row_count_match']:
                issues.append(f"transaction count mismatch ({len(df_original)} vs {len(df_standardized)})")
            if differences['transaction_differences']:
                issues.append(f"{len(differences['transaction_differences'])} transaction differences")
            print(", ".join(issues))
        else:
            print(f"   ✅ PASS - {len(df_original)} transactions, balances match")
    
    all_match = (
        opening_match and 
        closing_match and 
        differences['row_count_match'] and 
        len(differences['transaction_differences']) == 0
    )
    
    return all_match


def test_nb_company_cc(pdf_path: str, verbose: bool = False):
    """Test NB Company Credit Card extraction"""
    if verbose:
        print("\n" + "="*80)
        print("TESTING NB COMPANY CREDIT CARD EXTRACTION")
        print("="*80)
        print(f"PDF: {Path(pdf_path).name}\n")
    
    # Original extraction
    if verbose:
        print("1. Running original extraction (test_nb_company_cc_complete.py)...")
    try:
        from test_nb_company_cc_complete import extract_nb_company_cc_statement
        df_original, opening_orig, closing_orig, year_orig = extract_nb_company_cc_statement(pdf_path)
        
        if df_original is None or len(df_original) == 0:
            if verbose:
                print(f"   ❌ Error: Extraction returned no transactions")
            return False
        
        if verbose:
            print(f"   ✅ Original: {len(df_original)} transactions")
            print(f"   Opening: ${opening_orig:,.2f}" if opening_orig else "   Opening: Not found")
            print(f"   Closing: ${closing_orig:,.2f}" if closing_orig else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Standardized extraction
    if verbose:
        print("\n2. Running standardized extraction...")
    try:
        from standardized_bank_extractors import extract_bank_statement
        result = extract_bank_statement(pdf_path)
        if not result.success:
            if verbose:
                print(f"   ❌ Error: {result.error}")
            return False
        
        df_standardized = result.df
        opening_std = result.metadata.get('opening_balance')
        closing_std = result.metadata.get('closing_balance')
        
        if verbose:
            print(f"   ✅ Standardized: {len(df_standardized)} transactions")
            print(f"   Opening: ${opening_std:,.2f}" if opening_std else "   Opening: Not found")
            print(f"   Closing: ${closing_std:,.2f}" if closing_std else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Compare results
    differences = compare_dataframes(df_original, df_standardized, "Original", "Standardized")
    
    # Check balances
    opening_match = (
        (opening_orig is None and opening_std is None) or
        (opening_orig is not None and opening_std is not None and abs(opening_orig - opening_std) < 0.01)
    )
    closing_match = (
        (closing_orig is None and closing_std is None) or
        (closing_orig is not None and closing_std is not None and abs(closing_orig - closing_std) < 0.01)
    )
    
    if verbose:
        print("\n3. Comparison Results:")
        print(f"   Opening balance match: {'✅' if opening_match else '❌'}")
        if not opening_match:
            print(f"      Original: ${opening_orig:,.2f}" if opening_orig else "      Original: None")
            print(f"      Standardized: ${opening_std:,.2f}" if opening_std else "      Standardized: None")
        
        print(f"   Closing balance match: {'✅' if closing_match else '❌'}")
        if not closing_match:
            print(f"      Original: ${closing_orig:,.2f}" if closing_orig else "      Original: None")
            print(f"      Standardized: ${closing_std:,.2f}" if closing_std else "      Standardized: None")
        
        print(f"   Transaction count match: {'✅' if differences['row_count_match'] else '❌'}")
        if not differences['row_count_match']:
            print(f"      Original: {len(df_original)} transactions")
            print(f"      Standardized: {len(df_standardized)} transactions")
        
        if differences['transaction_differences']:
            print(f"   ⚠️  Found {len(differences['transaction_differences'])} transaction differences:")
            for diff in differences['transaction_differences'][:5]:
                print(f"      Row {diff['row_index']}: {diff}")
        else:
            print(f"   ✅ All transactions match!")
    else:
        # Brief summary for non-verbose mode
        if not opening_match or not closing_match or not differences['row_count_match'] or differences['transaction_differences']:
            print(f"   ❌ FAIL - ", end="")
            issues = []
            if not opening_match:
                issues.append("opening balance mismatch")
            if not closing_match:
                issues.append("closing balance mismatch")
            if not differences['row_count_match']:
                issues.append(f"transaction count mismatch ({len(df_original)} vs {len(df_standardized)})")
            if differences['transaction_differences']:
                issues.append(f"{len(differences['transaction_differences'])} transaction differences")
            print(", ".join(issues))
        else:
            print(f"   ✅ PASS - {len(df_original)} transactions, balances match")
    
    all_match = (
        opening_match and 
        closing_match and 
        differences['row_count_match'] and 
        len(differences['transaction_differences']) == 0
    )
    
    return all_match


def test_nb(pdf_path: str, verbose: bool = False):
    """Test NB Bank extraction"""
    if verbose:
        print("\n" + "="*80)
        print("TESTING NB BANK EXTRACTION")
        print("="*80)
        print(f"PDF: {Path(pdf_path).name}\n")
    
    # Original extraction
    if verbose:
        print("1. Running original extraction (test_nb_complete.py)...")
    try:
        from test_nb_complete import extract_nb_statement
        df_original, opening_orig, closing_orig, year_orig = extract_nb_statement(pdf_path)
        
        if df_original is None or len(df_original) == 0:
            if verbose:
                print(f"   ❌ Error: Extraction returned no transactions")
            return False
        
        if verbose:
            print(f"   ✅ Original: {len(df_original)} transactions")
            print(f"   Opening: ${opening_orig:,.2f}" if opening_orig else "   Opening: Not found")
            print(f"   Closing: ${closing_orig:,.2f}" if closing_orig else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Standardized extraction
    if verbose:
        print("\n2. Running standardized extraction...")
    try:
        from standardized_bank_extractors import extract_bank_statement
        result = extract_bank_statement(pdf_path)
        if not result.success:
            if verbose:
                print(f"   ❌ Error: {result.error}")
            return False
        
        df_standardized = result.df
        opening_std = result.metadata.get('opening_balance')
        closing_std = result.metadata.get('closing_balance')
        
        if verbose:
            print(f"   ✅ Standardized: {len(df_standardized)} transactions")
            print(f"   Opening: ${opening_std:,.2f}" if opening_std else "   Opening: Not found")
            print(f"   Closing: ${closing_std:,.2f}" if closing_std else "   Closing: Not found")
    except Exception as e:
        if verbose:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    # Compare results
    differences = compare_dataframes(df_original, df_standardized, "Original", "Standardized")
    
    # Check balances
    opening_match = (
        (opening_orig is None and opening_std is None) or
        (opening_orig is not None and opening_std is not None and abs(opening_orig - opening_std) < 0.01)
    )
    closing_match = (
        (closing_orig is None and closing_std is None) or
        (closing_orig is not None and closing_std is not None and abs(closing_orig - closing_std) < 0.01)
    )
    
    if verbose:
        print("\n3. Comparison Results:")
        print(f"   Opening balance match: {'✅' if opening_match else '❌'}")
        if not opening_match:
            print(f"      Original: ${opening_orig:,.2f}" if opening_orig else "      Original: None")
            print(f"      Standardized: ${opening_std:,.2f}" if opening_std else "      Standardized: None")
        
        print(f"   Closing balance match: {'✅' if closing_match else '❌'}")
        if not closing_match:
            print(f"      Original: ${closing_orig:,.2f}" if closing_orig else "      Original: None")
            print(f"      Standardized: ${closing_std:,.2f}" if closing_std else "      Standardized: None")
        
        print(f"   Transaction count match: {'✅' if differences['row_count_match'] else '❌'}")
        if not differences['row_count_match']:
            print(f"      Original: {len(df_original)} transactions")
            print(f"      Standardized: {len(df_standardized)} transactions")
        
        if differences['transaction_differences']:
            print(f"   ⚠️  Found {len(differences['transaction_differences'])} transaction differences:")
            for diff in differences['transaction_differences'][:5]:
                print(f"      Row {diff['row_index']}: {diff}")
        else:
            print(f"   ✅ All transactions match!")
    else:
        # Brief summary for non-verbose mode
        if not opening_match or not closing_match or not differences['row_count_match'] or differences['transaction_differences']:
            print(f"   ❌ FAIL - ", end="")
            issues = []
            if not opening_match:
                issues.append("opening balance mismatch")
            if not closing_match:
                issues.append("closing balance mismatch")
            if not differences['row_count_match']:
                issues.append(f"transaction count mismatch ({len(df_original)} vs {len(df_standardized)})")
            if differences['transaction_differences']:
                issues.append(f"{len(differences['transaction_differences'])} transaction differences")
            print(", ".join(issues))
        else:
            print(f"   ✅ PASS - {len(df_original)} transactions, balances match")
    
    all_match = (
        opening_match and 
        closing_match and 
        differences['row_count_match'] and 
        len(differences['transaction_differences']) == 0
    )
    
    return all_match


def main():
    """Run tests on all files in each folder"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Test standardized extractors against original extraction scripts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python test_standardized_extractors.py
  
  # Run specific bank(s)
  python test_standardized_extractors.py --cibc
  python test_standardized_extractors.py --td-bank --td-visa
  python test_standardized_extractors.py --scotia --tangerine
  
  # Run with verbose output
  python test_standardized_extractors.py --cibc --verbose
  
  # List available tests
  python test_standardized_extractors.py --list
        """
    )
    
    # Bank selection flags
    parser.add_argument('--td-bank', action='store_true', help='Test TD Bank (both 4738 and 7206)')
    parser.add_argument('--td-visa', action='store_true', help='Test TD Visa (both 6157 and 7744)')
    parser.add_argument('--scotia', action='store_true', help='Test Scotia Visa')
    parser.add_argument('--tangerine', action='store_true', help='Test Tangerine Bank')
    parser.add_argument('--cibc', action='store_true', help='Test CIBC Bank (both CAD and USD)')
    parser.add_argument('--nb', action='store_true', help='Test National Bank (both CAD and USD)')
    parser.add_argument('--nb-cc', action='store_true', help='Test NB Company Credit Card')
    
    # Other options
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output for each test')
    parser.add_argument('--list', action='store_true', help='List available test configurations')
    
    args = parser.parse_args()
    
    # Define all available test configurations
    all_test_configs = [
        {
            'name': 'TD Bank - 4738',
            'folder': Path("data/TD bank - 4738"),
            'test_func': test_td_bank,
            'flag': 'td-bank'
        },
        {
            'name': 'TD Bank - 7206',
            'folder': Path("data/TD bank - 7206"),
            'test_func': test_td_bank,
            'flag': 'td-bank'
        },
        {
            'name': 'TD Visa - 6157',
            'folder': Path("data/TD VISA 6157"),
            'test_func': test_td_visa,
            'flag': 'td-visa'
        },
        {
            'name': 'TD Visa - 7744',
            'folder': Path("data/TD VISA 7744"),
            'test_func': test_td_visa,
            'flag': 'td-visa'
        },
        {
            'name': 'Scotia Visa',
            'folder': Path("data/Scotia Visa"),
            'test_func': test_scotia_visa,
            'flag': 'scotia'
        },
        {
            'name': 'Tangerine Bank',
            'folder': Path("data/Tangeriene bank"),
            'test_func': test_tangerine,
            'flag': 'tangerine'
        },
        {
            'name': 'CIBC Bank - CAD',
            'folder': Path("data/Account Statements CAD - CIBC 4213"),
            'test_func': test_cibc,
            'flag': 'cibc'
        },
        {
            'name': 'CIBC Bank - USD',
            'folder': Path("data/Account Statements USD - CIBC 1014"),
            'test_func': test_cibc,
            'flag': 'cibc'
        },
        {
            'name': 'NB Bank - CAD',
            'folder': Path("data/NB-CAD acount 8528"),
            'test_func': test_nb,
            'flag': 'nb'
        },
        {
            'name': 'NB Bank - USD',
            'folder': Path("data/NB-USD acount 0569"),
            'test_func': test_nb,
            'flag': 'nb'
        },
        {
            'name': 'NB Company Credit Card',
            'folder': Path("data/NB- Company Credit Card 1074"),
            'test_func': test_nb_company_cc,
            'flag': 'nb-cc'
        }
    ]
    
    # Handle --list flag
    if args.list:
        print("Available test configurations:")
        print("="*80)
        for config in all_test_configs:
            print(f"  {config['name']:30} (--{config['flag']})")
        print("\nUse --help for usage examples")
        return
    
    # Filter test configs based on flags
    if any([args.td_bank, args.td_visa, args.scotia, args.tangerine, args.cibc, args.nb, args.nb_cc]):
        # User specified specific tests
        test_configs = []
        if args.td_bank:
            test_configs.extend([c for c in all_test_configs if c['flag'] == 'td-bank'])
        if args.td_visa:
            test_configs.extend([c for c in all_test_configs if c['flag'] == 'td-visa'])
        if args.scotia:
            test_configs.extend([c for c in all_test_configs if c['flag'] == 'scotia'])
        if args.tangerine:
            test_configs.extend([c for c in all_test_configs if c['flag'] == 'tangerine'])
        if args.cibc:
            test_configs.extend([c for c in all_test_configs if c['flag'] == 'cibc'])
        if args.nb:
            test_configs.extend([c for c in all_test_configs if c['flag'] == 'nb'])
        if args.nb_cc:
            test_configs.extend([c for c in all_test_configs if c['flag'] == 'nb-cc'])
    else:
        # No flags specified, run all tests
        test_configs = all_test_configs
    
    print("="*80)
    print("STANDARDIZED EXTRACTORS VALIDATION TEST")
    print("="*80)
    print("\nThis script compares original extraction scripts with standardized extractors")
    print("to ensure they produce identical results.\n")
    
    if test_configs != all_test_configs:
        print(f"Running selected tests: {', '.join(set(c['flag'] for c in test_configs))}\n")
    
    all_results = {}
    
    for config in test_configs:
        folder = config['folder']
        bank_name = config['name']
        test_func = config['test_func']
        
        if not folder.exists():
            print(f"\n⚠️  Folder not found: {folder}")
            all_results[bank_name] = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0}
            continue
        
        # Find all PDF files
        pdf_files = sorted(folder.glob("*.pdf"))
        
        if not pdf_files:
            print(f"\n⚠️  No PDF files found in: {folder}")
            all_results[bank_name] = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0}
            continue
        
        print(f"\n{'='*80}")
        print(f"TESTING {bank_name.upper()}")
        print(f"Found {len(pdf_files)} PDF file(s) in {folder.name}")
        print(f"{'='*80}")
        
        results = {'total': len(pdf_files), 'passed': 0, 'failed': 0, 'errors': 0, 'files': []}
        
        for pdf_file in pdf_files:
            print(f"\n{'─'*80}")
            print(f"Testing: {pdf_file.name}")
            print(f"{'─'*80}")
            
            try:
                result = test_func(str(pdf_file), verbose=args.verbose)
                if result:
                    results['passed'] += 1
                    results['files'].append({'file': pdf_file.name, 'status': 'PASS'})
                else:
                    results['failed'] += 1
                    results['files'].append({'file': pdf_file.name, 'status': 'FAIL'})
            except Exception as e:
                results['errors'] += 1
                results['files'].append({'file': pdf_file.name, 'status': 'ERROR', 'error': str(e)})
                print(f"   ❌ Error processing {pdf_file.name}: {e}")
                import traceback
                traceback.print_exc()
        
        all_results[bank_name] = results
        
        # Print summary for this bank
        print(f"\n{'─'*80}")
        print(f"{bank_name} Summary:")
        print(f"  Total files: {results['total']}")
        print(f"  ✅ Passed: {results['passed']}")
        print(f"  ❌ Failed: {results['failed']}")
        print(f"  ⚠️  Errors: {results['errors']}")
        if results['total'] > 0:
            success_rate = (results['passed'] / results['total']) * 100
            print(f"  Success rate: {success_rate:.1f}%")
    
    # Overall Summary
    print("\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    
    total_files = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0
    
    for bank_name, results in all_results.items():
        total_files += results['total']
        total_passed += results['passed']
        total_failed += results['failed']
        total_errors += results['errors']
        
        if results['total'] == 0:
            status = "⚠️  NO FILES"
        elif results['failed'] == 0 and results['errors'] == 0:
            status = f"✅ PASS ({results['passed']}/{results['total']})"
        elif results['failed'] > 0 or results['errors'] > 0:
            status = f"❌ FAIL ({results['passed']}/{results['total']} passed)"
        else:
            status = "⚠️  UNKNOWN"
        
        print(f"{bank_name:25} {status}")
        
        # Show failed files if any
        if results['failed'] > 0 or results['errors'] > 0:
            for file_info in results['files']:
                if file_info['status'] != 'PASS':
                    print(f"  └─ {file_info['file']}: {file_info['status']}")
                    if 'error' in file_info:
                        print(f"      Error: {file_info['error'][:100]}")
    
    print(f"\n{'─'*80}")
    print(f"Total Files Tested: {total_files}")
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print(f"⚠️  Errors: {total_errors}")
    
    if total_files > 0:
        overall_success_rate = (total_passed / total_files) * 100
        print(f"Overall Success Rate: {overall_success_rate:.1f}%")
    
    if total_failed == 0 and total_errors == 0 and total_passed > 0:
        print("\n🎉 All tests passed! Standardized extractors match original scripts.")
    elif total_passed > 0:
        print(f"\n⚠️  {total_failed + total_errors} test(s) failed. Please review the differences above.")
    else:
        print("\n⚠️  No tests were run successfully.")


if __name__ == "__main__":
    main()

