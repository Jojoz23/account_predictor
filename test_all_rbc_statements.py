#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test RBC extractor on all RBC folders"""

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

def test_rbc_folder(folder_path):
    """Test all PDFs in an RBC folder"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder not found: {folder_path}")
        return []
    
    pdf_files = sorted(folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"⚠️  No PDF files found in {folder_path}")
        return []
    
    print(f"\n{'='*80}")
    print(f"Testing folder: {folder.name}")
    print(f"{'='*80}")
    print(f"Found {len(pdf_files)} PDF file(s)\n")
    
    results = []
    
    for pdf_file in pdf_files:
        print("-"*80)
        print(f"Testing: {pdf_file.name}")
        print("-"*80)
        
        try:
            df, opening, closing, year = extract_rbc_chequing_statement(str(pdf_file))
            
            if df is None:
                results.append({
                    'folder': folder.name,
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
                'folder': folder.name,
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
                'folder': folder.name,
                'file': pdf_file.name,
                'status': 'ERROR',
                'error': str(e)
            })
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    return results

def main():
    # Find all RBC folders
    data_dir = Path("data")
    rbc_folders = []
    
    # Check for RBC folders
    for folder in data_dir.iterdir():
        if folder.is_dir() and 'RBC' in folder.name.upper():
            rbc_folders.append(folder)
    
    if not rbc_folders:
        print("❌ No RBC folders found in data directory")
        return
    
    print("="*80)
    print("TESTING ALL RBC STATEMENTS")
    print("="*80)
    print(f"Found {len(rbc_folders)} RBC folder(s)\n")
    
    all_results = []
    
    for folder in sorted(rbc_folders):
        results = test_rbc_folder(folder)
        all_results.extend(results)
    
    # Overall Summary
    print("\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    
    passed = [r for r in all_results if r.get('status') == 'PASS']
    failed = [r for r in all_results if r.get('status') == 'FAIL']
    errors = [r for r in all_results if r.get('status') == 'ERROR']
    
    print(f"\nTotal files: {len(all_results)}")
    print(f"✅ Passed: {len(passed)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"⚠️  Errors: {len(errors)}")
    
    if len(all_results) > 0:
        success_rate = (len(passed) / len(all_results)) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    # Group by folder
    print("\n" + "-"*80)
    print("Results by folder:")
    print("-"*80)
    for folder in sorted(rbc_folders):
        folder_results = [r for r in all_results if r['folder'] == folder.name]
        folder_passed = [r for r in folder_results if r.get('status') == 'PASS']
        print(f"\n{folder.name}: {len(folder_passed)}/{len(folder_results)} passing")
    
    if failed:
        print(f"\n❌ Failed files:")
        for r in failed:
            print(f"   - {r['folder']}/{r['file']}")
            if r.get('final_rb') and r.get('closing'):
                diff = abs(r['final_rb'] - r['closing'])
                print(f"     Difference: ${diff:,.2f}")
    
    if errors:
        print(f"\n⚠️  Error files:")
        for r in errors:
            print(f"   - {r['folder']}/{r['file']}: {r.get('error', 'Unknown error')}")
    
    if len(passed) == len(all_results) and len(all_results) > 0:
        print("\n🎉 All tests passed!")

if __name__ == "__main__":
    main()
