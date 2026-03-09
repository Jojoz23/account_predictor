#!/usr/bin/env python3
"""
Batch test all CIBC CAD statements
"""

import sys
from pathlib import Path
from test_cibc_cad_complete import extract_cibc_cad_statement

def test_all_cibc_cad():
    """Test all CIBC CAD PDFs"""
    pdf_dir = Path("data/Account Statements CAD - CIBC 4213")
    
    if not pdf_dir.exists():
        print(f"Directory not found: {pdf_dir}")
        return
    
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {pdf_dir}")
        return
    
    print(f"="*80)
    print(f"BATCH TEST: CIBC CAD Statements")
    print(f"="*80)
    print(f"\nFound {len(pdf_files)} PDF files\n")
    
    results = []
    
    for pdf_file in pdf_files:
        print(f"\n{'='*80}")
        print(f"Processing: {pdf_file.name}")
        print(f"{'='*80}")
        
        try:
            result = extract_cibc_cad_statement(str(pdf_file))
            
            if result and result['transactions']:
                num_trans = len(result['transactions'])
                opening = result.get('opening_balance')
                closing = result.get('closing_balance')
                
                results.append({
                    'file': pdf_file.name,
                    'status': 'SUCCESS',
                    'transactions': num_trans,
                    'opening_balance': opening,
                    'closing_balance': closing,
                    'year': result.get('statement_year')
                })
                
                print(f"\n[OK] {pdf_file.name}: {num_trans} transactions")
            else:
                results.append({
                    'file': pdf_file.name,
                    'status': 'FAILED',
                    'transactions': 0
                })
                print(f"\n[FAILED] {pdf_file.name}: No transactions extracted")
        except Exception as e:
            results.append({
                'file': pdf_file.name,
                'status': 'ERROR',
                'error': str(e)
            })
            print(f"\n[ERROR] {pdf_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    success = [r for r in results if r['status'] == 'SUCCESS']
    failed = [r for r in results if r['status'] != 'SUCCESS']
    
    print(f"\nTotal files: {len(results)}")
    print(f"Success: {len(success)}")
    print(f"Failed: {len(failed)}")
    
    if success:
        total_trans = sum(r['transactions'] for r in success)
        print(f"\nTotal transactions extracted: {total_trans}")
        avg_trans = total_trans / len(success)
        print(f"Average transactions per file: {avg_trans:.1f}")
    
    if failed:
        print(f"\nFailed files:")
        for r in failed:
            print(f"  - {r['file']}: {r.get('error', 'No transactions')}")

if __name__ == "__main__":
    test_all_cibc_cad()
