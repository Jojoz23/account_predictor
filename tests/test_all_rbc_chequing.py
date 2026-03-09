#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test RBC Chequing extractor on all statements"""

import sys
import io
from pathlib import Path

# Fix encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except:
        pass

from test_rbc_chequing_complete import extract_rbc_chequing_statement

def main():
    rbc_folder = Path("data/RBC Chequing 3143 Jan 22, 2025 - Dec 22, 2025")
    
    if not rbc_folder.exists():
        print(f"❌ Folder not found: {rbc_folder}")
        return
    
    pdf_files = sorted(rbc_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ No PDF files found in {rbc_folder}")
        return
    
    print("="*80)
    print("TESTING ALL RBC CHEQUING STATEMENTS")
    print("="*80)
    print(f"Found {len(pdf_files)} PDF file(s)\n")
    
    results = []
    
    for pdf_file in pdf_files:
        print("\n" + "-"*80)
        print(f"Testing: {pdf_file.name}")
        print("-"*80)
        
        try:
            df, opening, closing, year = extract_rbc_chequing_statement(str(pdf_file))
            
            if df is None:
                results.append({
                    'file': pdf_file.name,
                    'status': 'ERROR',
                    'error': 'No transactions extracted'
                })
                print(f"   ❌ ERROR: No transactions extracted")
                continue
            
            # Check running balance match
            running_match = False
            final_rb = None
            if opening is not None and 'Running_Balance' in df.columns:
                final_rb = df['Running_Balance'].iloc[-1]
                if closing is not None:
                    diff = abs(final_rb - closing)
                    running_match = diff < 0.01
            
            result = {
                'file': pdf_file.name,
                'status': 'PASS' if running_match else 'FAIL',
                'transactions': len(df),
                'opening': opening,
                'closing': closing,
                'final_rb': final_rb,
                'match': running_match
            }
            results.append(result)
            
            print(f"   ✅ Transactions: {len(df)}")
            print(f"   Opening: ${opening:,.2f}" if opening else "   Opening: Not found")
            print(f"   Closing: ${closing:,.2f}" if closing else "   Closing: Not found")
            if final_rb:
                print(f"   Final Running Balance: ${final_rb:,.2f}")
                if closing:
                    diff = abs(final_rb - closing)
                    if diff < 0.01:
                        print(f"   ✅ Running balance matches closing balance!")
                    else:
                        print(f"   ⚠️  Difference: ${diff:,.2f}")
            
        except Exception as e:
            results.append({
                'file': pdf_file.name,
                'status': 'ERROR',
                'error': str(e)
            })
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    passed = [r for r in results if r.get('status') == 'PASS']
    failed = [r for r in results if r.get('status') == 'FAIL']
    errors = [r for r in results if r.get('status') == 'ERROR']
    
    print(f"\nTotal files: {len(results)}")
    print(f"✅ Passed: {len(passed)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"⚠️  Errors: {len(errors)}")
    
    if len(results) > 0:
        success_rate = (len(passed) / len(results)) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    if failed:
        print(f"\n❌ Failed files:")
        for r in failed:
            print(f"   - {r['file']}")
            if r.get('final_rb') and r.get('closing'):
                diff = abs(r['final_rb'] - r['closing'])
                print(f"     Difference: ${diff:,.2f}")
    
    if errors:
        print(f"\n⚠️  Error files:")
        for r in errors:
            print(f"   - {r['file']}: {r.get('error', 'Unknown error')}")
    
    if len(passed) == len(results) and len(results) > 0:
        print("\n🎉 All tests passed!")

if __name__ == "__main__":
    main()
