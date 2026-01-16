#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test all NB Company Credit Card statements
"""

from pathlib import Path
import pandas as pd
import re
from test_nb_company_cc_complete import extract_nb_company_cc_statement

def test_all_files(folder_path, label):
    """Test all PDFs in a folder"""
    pdf_files = sorted(Path(folder_path).glob("*.pdf"))
    
    if not pdf_files:
        print(f"⚠️  No PDF files found in {folder_path}")
        return []
    
    print(f"\n{'='*80}")
    print(f"TESTING {label}: {folder_path}")
    print(f"{'='*80}")
    print(f"Found {len(pdf_files)} PDF file(s)\n")
    
    results = []
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] {pdf_file.name}")
        print("-" * 80)
        
        try:
            df, opening, closing, year = extract_nb_company_cc_statement(str(pdf_file))
            
            balance_match = False
            final_rb = None
            balance_diff = None
            date_issues = []
            
            if not df.empty and 'Running_Balance' in df.columns and len(df) > 0:
                final_rb = df['Running_Balance'].iloc[-1]
                if closing is not None:
                    balance_diff = abs(final_rb - closing)
                    balance_match = balance_diff < 0.01
                
                # Check dates use correct year
                if year and 'Date' in df.columns and len(df) > 0:
                    # Check if dates are within statement period
                    # Get statement period from filename (e.g., "Dec 8 2024 - Jan 2 2025")
                    filename = pdf_file.stem
                    period_match = re.search(r'(\d{1,2}\.\s+)?([A-Z][a-z]+)\s+(\d{1,2})\s+(\d{4})\s+-\s+([A-Z][a-z]+)\s+(\d{1,2})\s+(\d{4})', filename)
                    if period_match:
                        start_month_name = period_match.group(2)
                        start_year = int(period_match.group(4))
                        end_month_name = period_match.group(5)
                        end_year = int(period_match.group(7))
                        
                        month_map = {
                            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                        }
                        start_month = month_map.get(start_month_name, 1)
                        end_month = month_map.get(end_month_name, 1)
                        
                        # Check first and last dates
                        first_date = pd.to_datetime(df['Date'].iloc[0])
                        last_date = pd.to_datetime(df['Date'].iloc[-1])
                        
                        expected_start = pd.to_datetime(f"{start_year}-{start_month:02d}-01")
                        expected_end = pd.to_datetime(f"{end_year}-{end_month:02d}-28")
                        
                        if first_date.year < start_year or first_date.year > end_year + 1:
                            date_issues.append(f"First date {first_date.date()} outside period {start_year}-{end_year}")
                        if last_date.year < start_year or last_date.year > end_year + 1:
                            date_issues.append(f"Last date {last_date.date()} outside period {start_year}-{end_year}")
            
            status = '✅' if balance_match else ('⚠️' if closing is None else '❌')
            print(f"  {status} Transactions: {len(df)}")
            print(f"      Opening: ${opening:,.2f}" if opening else "      Opening: N/A")
            print(f"      Closing: ${closing:,.2f}" if closing else "      Closing: N/A")
            print(f"      Statement Year: {year}" if year else "      Statement Year: N/A")
            
            if final_rb is not None:
                print(f"      Final Running Balance: ${final_rb:,.2f}")
                if closing is not None:
                    if balance_match:
                        print(f"      ✅ Balance matches!")
                    else:
                        print(f"      ⚠️  Balance difference: ${balance_diff:,.2f}")
            
            if date_issues:
                print(f"      ⚠️  Date issues:")
                for issue in date_issues:
                    print(f"         - {issue}")
            elif len(df) > 0 and 'Date' in df.columns:
                print(f"      ✅ Dates verified")
            
            results.append({
                'file': pdf_file.name,
                'transactions': len(df),
                'opening': opening,
                'closing': closing,
                'final_rb': final_rb,
                'balance_match': balance_match,
                'balance_diff': balance_diff,
                'date_issues': len(date_issues) > 0,
                'status': 'Success' if balance_match and not date_issues else 'Warning'
            })
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'file': pdf_file.name,
                'transactions': 0,
                'status': 'Error',
                'error': str(e)
            })
    
    return results


if __name__ == "__main__":
    import sys
    import io
    
    # Fix encoding for Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    print("="*80)
    print("TESTING ALL NB COMPANY CREDIT CARD STATEMENTS")
    print("="*80)
    
    # Test Company Credit Card folder
    cc_results = test_all_files("data/NB- Company Credit Card 1074", "NB Company Credit Card")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    all_results = cc_results
    
    total_files = len(all_results)
    successful = len([r for r in all_results if r.get('status') == 'Success'])
    warnings = len([r for r in all_results if r.get('status') == 'Warning'])
    errors = len([r for r in all_results if r.get('status') == 'Error'])
    total_transactions = sum([r.get('transactions', 0) for r in all_results])
    
    print(f"\nTotal files: {total_files}")
    print(f"  ✅ Successful: {successful}")
    print(f"  ⚠️  Warnings: {warnings}")
    print(f"  ❌ Errors: {errors}")
    print(f"\nTotal transactions: {total_transactions}")
    
    if warnings > 0:
        print(f"\n⚠️  Files with issues:")
        for r in all_results:
            if r.get('status') == 'Warning':
                issues = []
                if not r.get('balance_match'):
                    issues.append(f"balance diff = ${r.get('balance_diff', 0):,.2f}")
                if r.get('date_issues'):
                    issues.append("date issues")
                print(f"    {r['file']}: {', '.join(issues)}")
    
    if errors > 0:
        print(f"\n❌ Files with errors:")
        for r in all_results:
            if r.get('status') == 'Error':
                print(f"    {r['file']}: {r.get('error', 'Unknown error')}")
