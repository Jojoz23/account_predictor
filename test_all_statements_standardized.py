#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test all bank statements using standardized extractors vs original scripts and output to file"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from standardized_bank_extractors import extract_bank_statement
from pathlib import Path
import pandas as pd
from datetime import datetime

# Import original extraction functions for comparison
from test_td_bank_complete import extract_td_bank_statement_camelot
from standardized_bank_extractors import extract_td_visa_statement, extract_scotia_visa_statement
from extract_tangerine_bank import extract_tangerine_bank_statement

def compare_dataframes(df1: pd.DataFrame, df2: pd.DataFrame) -> dict:
    """Compare two DataFrames and return differences"""
    differences = {
        'row_count_match': len(df1) == len(df2),
        'row_count_diff': abs(len(df1) - len(df2)),
        'column_match': set(df1.columns) == set(df2.columns),
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
        
        if row_diff:
            row_diff['row_index'] = idx
            differences['transaction_differences'].append(row_diff)
    
    return differences

# Define folders and their extraction functions
test_configs = [
    {
        'name': 'TD Bank - 4738',
        'folder': Path("data/TD bank - 4738"),
        'original_func': extract_td_bank_statement_camelot,
        'is_credit_card': False
    },
    {
        'name': 'TD Bank - 7206',
        'folder': Path("data/TD bank - 7206"),
        'original_func': extract_td_bank_statement_camelot,
        'is_credit_card': False
    },
    {
        'name': 'TD Visa - 6157',
        'folder': Path("data/TD VISA 6157"),
        'original_func': extract_td_visa_statement,
        'is_credit_card': True
    },
    {
        'name': 'TD Visa - 7744',
        'folder': Path("data/TD VISA 7744"),
        'original_func': extract_td_visa_statement,
        'is_credit_card': True
    },
    {
        'name': 'Scotia Visa',
        'folder': Path("data/Scotia Visa"),
        'original_func': extract_scotia_visa_statement,
        'is_credit_card': True
    },
    {
        'name': 'Tangerine Bank',
        'folder': Path("data/Tangeriene bank"),
        'original_func': extract_tangerine_bank_statement,
        'is_credit_card': False
    }
]

# Output file
output_file = "test_all_statements_comparison.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("="*80 + "\n")
    f.write("TESTING ALL BANK STATEMENTS: STANDARDIZED vs ORIGINAL EXTRACTORS\n")
    f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("="*80 + "\n\n")
    
    all_results = {}
    total_files = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0
    
    for config in test_configs:
        folder = config['folder']
        bank_name = config['name']
        original_func = config['original_func']
        is_credit_card = config['is_credit_card']
        
        if not folder.exists():
            f.write(f"\n⚠️  Folder not found: {folder}\n")
            all_results[bank_name] = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0}
            continue
        
        # Find all PDF files
        pdf_files = sorted(folder.glob("*.pdf"))
        
        if not pdf_files:
            f.write(f"\n⚠️  No PDF files found in: {folder}\n")
            all_results[bank_name] = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0}
            continue
        
        f.write(f"\n{'='*80}\n")
        f.write(f"TESTING {bank_name.upper()}\n")
        f.write(f"Found {len(pdf_files)} PDF file(s) in {folder.name}\n")
        f.write(f"{'='*80}\n\n")
        
        results = {'total': len(pdf_files), 'passed': 0, 'failed': 0, 'errors': 0, 'files': []}
        
        for pdf_file in pdf_files:
            f.write(f"\n{'-'*80}\n")
            f.write(f"Testing: {pdf_file.name}\n")
            f.write(f"{'-'*80}\n")
            
            try:
                # Test original extraction
                f.write("\n1. ORIGINAL EXTRACTION:\n")
                try:
                    if is_credit_card:
                        df_orig, op_orig, cl_orig, yr_orig = original_func(str(pdf_file))
                    else:
                        df_orig, op_orig, cl_orig, yr_orig = original_func(str(pdf_file))
                    
                    if df_orig is None or len(df_orig) == 0:
                        f.write("   ❌ No transactions extracted\n")
                        results['failed'] += 1
                        results['files'].append({'file': pdf_file.name, 'status': 'FAIL', 'reason': 'No transactions'})
                        continue
                    
                    f.write(f"   ✅ Transactions: {len(df_orig)}\n")
                    f.write(f"   Opening: ${op_orig:,.2f}\n" if op_orig else "   Opening: Not found\n")
                    f.write(f"   Closing: ${cl_orig:,.2f}\n" if cl_orig else "   Closing: Not found\n")
                except Exception as e:
                    f.write(f"   ❌ Error: {e}\n")
                    results['errors'] += 1
                    results['files'].append({'file': pdf_file.name, 'status': 'ERROR', 'error': str(e)})
                    continue
                
                # Test standardized extraction
                f.write("\n2. STANDARDIZED EXTRACTION:\n")
                try:
                    result = extract_bank_statement(str(pdf_file))
                    
                    if not result.success:
                        f.write(f"   ❌ Error: {result.error}\n")
                        results['failed'] += 1
                        results['files'].append({'file': pdf_file.name, 'status': 'FAIL', 'reason': result.error})
                        continue
                    
                    df_std = result.df
                    op_std = result.metadata.get('opening_balance')
                    cl_std = result.metadata.get('closing_balance')
                    
                    f.write(f"   ✅ Transactions: {len(df_std)}\n")
                    f.write(f"   Opening: ${op_std:,.2f}\n" if op_std else "   Opening: Not found\n")
                    f.write(f"   Closing: ${cl_std:,.2f}\n" if cl_std else "   Closing: Not found\n")
                except Exception as e:
                    f.write(f"   ❌ Error: {e}\n")
                    results['errors'] += 1
                    results['files'].append({'file': pdf_file.name, 'status': 'ERROR', 'error': str(e)})
                    continue
                
                # Compare results
                f.write("\n3. COMPARISON:\n")
                
                # Compare transaction counts
                count_match = len(df_orig) == len(df_std)
                f.write(f"   Transaction count: {'✅ MATCH' if count_match else f'❌ DIFFERENT ({len(df_orig)} vs {len(df_std)})'}\n")
                
                # Compare balances
                op_match = (op_orig is None and op_std is None) or (op_orig is not None and op_std is not None and abs(op_orig - op_std) < 0.01)
                cl_match = (cl_orig is None and cl_std is None) or (cl_orig is not None and cl_std is not None and abs(cl_orig - cl_std) < 0.01)
                
                f.write(f"   Opening balance: {'✅ MATCH' if op_match else '❌ DIFFERENT'}\n")
                if not op_match:
                    f.write(f"      Original: ${op_orig:,.2f}\n" if op_orig else "      Original: None\n")
                    f.write(f"      Standardized: ${op_std:,.2f}\n" if op_std else "      Standardized: None\n")
                
                f.write(f"   Closing balance: {'✅ MATCH' if cl_match else '❌ DIFFERENT'}\n")
                if not cl_match:
                    f.write(f"      Original: ${cl_orig:,.2f}\n" if cl_orig else "      Original: None\n")
                    f.write(f"      Standardized: ${cl_std:,.2f}\n" if cl_std else "      Standardized: None\n")
                
                # Compare DataFrames if counts match
                if count_match and len(df_orig) > 0:
                    differences = compare_dataframes(df_orig, df_std)
                    if differences['transaction_differences']:
                        f.write(f"   Transaction differences: {len(differences['transaction_differences'])} found\n")
                        # Show first 3 differences
                        for diff in differences['transaction_differences'][:3]:
                            f.write(f"      Row {diff['row_index']}: {', '.join([f'{k}={v}' for k, v in diff.items() if k != 'row_index'])}\n")
                    else:
                        f.write("   Transaction data: ✅ MATCH\n")
                
                # Determine if test passed
                test_passed = count_match and op_match and cl_match and (not differences.get('transaction_differences', []) if count_match else False)
                
                if test_passed:
                    results['passed'] += 1
                    results['files'].append({'file': pdf_file.name, 'status': 'PASS'})
                    f.write("\n   ✅ TEST PASSED\n")
                else:
                    results['failed'] += 1
                    results['files'].append({'file': pdf_file.name, 'status': 'FAIL'})
                    f.write("\n   ❌ TEST FAILED\n")
                
            except Exception as e:
                results['errors'] += 1
                results['files'].append({'file': pdf_file.name, 'status': 'ERROR', 'error': str(e)})
                f.write(f"\n❌ EXCEPTION: {e}\n")
                import traceback
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
        
        all_results[bank_name] = results
        total_files += results['total']
        total_passed += results['passed']
        total_failed += results['failed']
        total_errors += results['errors']
        
        # Print summary for this bank
        f.write(f"\n{'-'*80}\n")
        f.write(f"{bank_name} Summary:\n")
        f.write(f"  Total files: {results['total']}\n")
        f.write(f"  ✅ Passed: {results['passed']}\n")
        f.write(f"  ❌ Failed: {results['failed']}\n")
        f.write(f"  ⚠️  Errors: {results['errors']}\n")
        if results['total'] > 0:
            success_rate = (results['passed'] / results['total']) * 100
            f.write(f"  Success rate: {success_rate:.1f}%\n")
    
    # Overall Summary
    f.write("\n" + "="*80 + "\n")
    f.write("OVERALL SUMMARY\n")
    f.write("="*80 + "\n")
    
    for bank_name, results in all_results.items():
        if results['total'] == 0:
            status = "⚠️  NO FILES"
        elif results['failed'] == 0 and results['errors'] == 0:
            status = f"✅ PASS ({results['passed']}/{results['total']})"
        elif results['failed'] > 0 or results['errors'] > 0:
            status = f"❌ FAIL ({results['passed']}/{results['total']} passed)"
        else:
            status = "⚠️  UNKNOWN"
        
        f.write(f"{bank_name:25} {status}\n")
        
        # Show failed files if any
        if results['failed'] > 0 or results['errors'] > 0:
            for file_info in results['files']:
                if file_info['status'] != 'PASS':
                    f.write(f"  └─ {file_info['file']}: {file_info['status']}\n")
                    if 'error' in file_info:
                        f.write(f"      Error: {file_info['error'][:100]}\n")
    
    f.write(f"\n{'-'*80}\n")
    f.write(f"Total Files Tested: {total_files}\n")
    f.write(f"✅ Passed: {total_passed}\n")
    f.write(f"❌ Failed: {total_failed}\n")
    f.write(f"⚠️  Errors: {total_errors}\n")
    
    if total_files > 0:
        overall_success_rate = (total_passed / total_files) * 100
        f.write(f"Overall Success Rate: {overall_success_rate:.1f}%\n")
    
    if total_failed == 0 and total_errors == 0 and total_passed > 0:
        f.write("\n🎉 All tests passed! Standardized extractors match original scripts.\n")
    elif total_passed > 0:
        f.write(f"\n⚠️  {total_failed + total_errors} test(s) failed. Please review the differences above.\n")
    else:
        f.write("\n⚠️  No tests were run successfully.\n")

print(f"\n{'='*80}")
print(f"Results written to: {output_file}")
print(f"{'='*80}")
