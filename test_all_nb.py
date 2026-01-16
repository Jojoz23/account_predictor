#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test all NB Bank statements (CAD and USD)
"""

from pathlib import Path
from test_nb_complete import extract_nb_statement

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
            df, opening, closing, year = extract_nb_statement(str(pdf_file))
            
            balance_match = False
            final_rb = None
            balance_diff = None
            
            if not df.empty and 'Running_Balance' in df.columns and len(df) > 0:
                final_rb = df['Running_Balance'].iloc[-1]
                if closing is not None:
                    balance_diff = abs(final_rb - closing)
                    balance_match = balance_diff < 0.01
            
            status = '✅' if balance_match else ('⚠️' if closing is None else '❌')
            print(f"  {status} Transactions: {len(df)}")
            print(f"      Opening: ${opening:,.2f}" if opening else "      Opening: N/A")
            print(f"      Closing: ${closing:,.2f}" if closing else "      Closing: N/A")
            
            if final_rb is not None:
                print(f"      Final Running Balance: ${final_rb:,.2f}")
                if closing is not None:
                    if balance_match:
                        print(f"      ✅ Balance matches!")
                    else:
                        print(f"      ⚠️  Balance difference: ${balance_diff:,.2f}")
            
            results.append({
                'file': pdf_file.name,
                'transactions': len(df),
                'opening': opening,
                'closing': closing,
                'final_rb': final_rb,
                'balance_match': balance_match,
                'balance_diff': balance_diff,
                'status': 'Success' if balance_match or closing is None else 'Warning'
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
    print("="*80)
    print("TESTING ALL NB BANK STATEMENTS")
    print("="*80)
    
    # Test CAD folder
    cad_results = test_all_files("data/NB-CAD acount 8528", "NB CAD")
    
    # Test USD folder
    usd_results = test_all_files("data/NB-USD acount 0569", "NB USD")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    all_results = cad_results + usd_results
    
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
        print(f"\n⚠️  Files with balance mismatches:")
        for r in all_results:
            if r.get('status') == 'Warning':
                print(f"    {r['file']}: diff = ${r.get('balance_diff', 0):,.2f}")
    
    if errors > 0:
        print(f"\n❌ Files with errors:")
        for r in all_results:
            if r.get('status') == 'Error':
                print(f"    {r['file']}: {r.get('error', 'Unknown error')}")
