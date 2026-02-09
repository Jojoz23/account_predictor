#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test all TD Bank statements from both folders (not TD Visa)"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from test_td_bank_complete import extract_td_bank_statement_camelot, extract_td_bank_statement
from pathlib import Path
import pandas as pd

# Get all TD bank PDFs from both folders (not TD Visa)
td_bank_folders = [
    Path("data/TD bank - 4738"),
    Path("data/TD bank - 7206")
]

pdf_files = []
for folder in td_bank_folders:
    if folder.exists():
        pdf_files.extend(sorted(folder.glob("*.pdf")))

print("="*70)
print("TESTING ALL TD BANK STATEMENTS (BOTH FOLDERS)")
print("="*70)
print(f"Found {len(pdf_files)} PDF files")
print(f"  From 'TD bank - 4738': {len(list(Path('data/TD bank - 4738').glob('*.pdf')))} files")
print(f"  From 'TD bank - 7206': {len(list(Path('data/TD bank - 7206').glob('*.pdf')))} files")
print()

results = []

for pdf_path in pdf_files:
    print("\n" + "="*70)
    print(f"Testing: {pdf_path.name}")
    print(f"Folder: {pdf_path.parent.name}")
    print("="*70)
    
    try:
        # Test PDFPlumber method
        print("\n--- PDFPlumber Method ---")
        df_pdfplumber, opening_p, closing_p, year_p = extract_td_bank_statement(str(pdf_path))
        
        # Test Camelot method
        print("\n--- Camelot Method ---")
        df_camelot, opening_c, closing_c, year_c = extract_td_bank_statement_camelot(str(pdf_path))
        
        # Compare results
        pdfplumber_count = len(df_pdfplumber) if df_pdfplumber is not None else 0
        camelot_count = len(df_camelot) if df_camelot is not None else 0
        
        pdfplumber_rb = None
        camelot_rb = None
        pdfplumber_match = None
        camelot_match = None
        
        if df_pdfplumber is not None and 'Running_Balance' in df_pdfplumber.columns:
            pdfplumber_rb = df_pdfplumber['Running_Balance'].iloc[-1]
            if closing_p:
                pdfplumber_match = abs(pdfplumber_rb - closing_p) < 0.01
        
        if df_camelot is not None and 'Running_Balance' in df_camelot.columns:
            camelot_rb = df_camelot['Running_Balance'].iloc[-1]
            if closing_c:
                camelot_match = abs(camelot_rb - closing_c) < 0.01
        
        result = {
            'file': pdf_path.name,
            'folder': pdf_path.parent.name,
            'pdfplumber': {
                'transactions': pdfplumber_count,
                'opening': opening_p,
                'closing': closing_p,
                'running_balance': pdfplumber_rb,
                'match': pdfplumber_match
            },
            'camelot': {
                'transactions': camelot_count,
                'opening': opening_c,
                'closing': closing_c,
                'running_balance': camelot_rb,
                'match': camelot_match
            }
        }
        results.append(result)
        
        # Print summary
        print(f"\n--- Summary for {pdf_path.name} ---")
        print(f"PDFPlumber: {pdfplumber_count} transactions, Opening: ${opening_p:,.2f}" if opening_p else f"PDFPlumber: {pdfplumber_count} transactions, Opening: Not found")
        print(f"  Final RB: ${pdfplumber_rb:,.2f}" if pdfplumber_rb else "  Final RB: N/A")
        print(f"  Closing: ${closing_p:,.2f}" if closing_p else "  Closing: Not found")
        print(f"  Match: {'YES' if pdfplumber_match else 'NO' if pdfplumber_match is False else 'UNKNOWN'}")
        
        print(f"\nCamelot: {camelot_count} transactions, Opening: ${opening_c:,.2f}" if opening_c else f"Camelot: {camelot_count} transactions, Opening: Not found")
        print(f"  Final RB: ${camelot_rb:,.2f}" if camelot_rb else "  Final RB: N/A")
        print(f"  Closing: ${closing_c:,.2f}" if closing_c else "  Closing: Not found")
        print(f"  Match: {'YES' if camelot_match else 'NO' if camelot_match is False else 'UNKNOWN'}")
        
        # Check if methods agree
        if pdfplumber_count == camelot_count:
            print(f"\nBoth methods extracted same number of transactions ({pdfplumber_count})")
        else:
            print(f"\nTransaction count differs: PDFPlumber={pdfplumber_count}, Camelot={camelot_count}")
        
        if opening_p and opening_c and abs(opening_p - opening_c) < 0.01:
            print(f"Opening balances match: ${opening_p:,.2f}")
        elif opening_p and opening_c:
            print(f"Opening balances differ: PDFPlumber=${opening_p:,.2f}, Camelot=${opening_c:,.2f}")
        
        if closing_p and closing_c and abs(closing_p - closing_c) < 0.01:
            print(f"Closing balances match: ${closing_p:,.2f}")
        elif closing_p and closing_c:
            print(f"Closing balances differ: PDFPlumber=${closing_p:,.2f}, Camelot=${closing_c:,.2f}")
            
    except Exception as e:
        print(f"\nERROR processing {pdf_path.name}: {e}")
        import traceback
        traceback.print_exc()
        results.append({
            'file': pdf_path.name,
            'folder': pdf_path.parent.name,
            'error': str(e)
        })

# Final summary
print("\n" + "="*70)
print("FINAL SUMMARY")
print("="*70)

successful = [r for r in results if 'error' not in r]
failed = [r for r in results if 'error' in r]

print(f"\nTotal files: {len(results)}")
print(f"Successful: {len(successful)}")
print(f"Failed: {len(failed)}")

# Count by folder
folder_counts = {}
for r in successful:
    folder = r.get('folder', 'Unknown')
    if folder not in folder_counts:
        folder_counts[folder] = {'total': 0, 'camelot_match': 0, 'pdfplumber_match': 0}
    folder_counts[folder]['total'] += 1
    if r['camelot']['match']:
        folder_counts[folder]['camelot_match'] += 1
    if r['pdfplumber']['match']:
        folder_counts[folder]['pdfplumber_match'] += 1

print("\n--- Results by Folder ---")
for folder, counts in folder_counts.items():
    print(f"\n{folder}:")
    print(f"  Total files: {counts['total']}")
    print(f"  Camelot balance match: {counts['camelot_match']}/{counts['total']}")
    print(f"  PDFPlumber balance match: {counts['pdfplumber_match']}/{counts['total']}")

if successful:
    print("\n--- Successful Extractions ---")
    for r in successful:
        p = r['pdfplumber']
        c = r['camelot']
        print(f"\n{r['folder']}/{r['file']}:")
        print(f"  PDFPlumber: {p['transactions']} txns, Match: {'YES' if p['match'] else 'NO' if p['match'] is False else 'UNKNOWN'}")
        print(f"  Camelot: {c['transactions']} txns, Match: {'YES' if c['match'] else 'NO' if c['match'] is False else 'UNKNOWN'}")

if failed:
    print("\n--- Failed Extractions ---")
    for r in failed:
        print(f"  {r['folder']}/{r['file']}: {r['error']}")



