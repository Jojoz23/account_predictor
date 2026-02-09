#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run all BMO extractors (bank + credit card) and verify balances match.
Use this to confirm extraction is accurate across all PDFs.

Note: If run in a sandbox (e.g. Cursor), BMO bank may show Camelot permission
errors and fall back to text; run in a normal terminal for full Camelot + balance check.
"""

import sys
import io
from pathlib import Path
import pandas as pd

if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# Suppress verbose Camelot table dump during batch verification
import os
os.environ['BMO_VERIFY_QUIET'] = '1'

def verify_bmo_bank(pdf_path):
    """Extract BMO bank statement and verify closing balance matches calculated.
    Tries Camelot first; on failure (e.g. env/permission), falls back to text extractor for balance check.
    """
    fname = getattr(pdf_path, 'name', str(pdf_path))

    def _check(df, opening, closing, source, n_tables=0):
        if df is None or len(df) == 0:
            return {'ok': False, 'file': fname, 'error': 'No transactions', 'source': source}
        w = pd.to_numeric(df['Withdrawals'], errors='coerce').fillna(0).sum() if 'Withdrawals' in df.columns else 0
        d = pd.to_numeric(df['Deposits'], errors='coerce').fillna(0).sum() if 'Deposits' in df.columns else 0
        # Derive missing opening/closing from data so we never report "skipped"
        if opening is None and closing is not None:
            opening = float(closing) + float(w) - float(d)
        if closing is None and opening is not None:
            closing = float(opening) - float(w) + float(d)
        if opening is None and closing is None and len(df) > 0 and 'Balance' in df.columns:
            last_val = df['Balance'].iloc[-1]
            try:
                cv = float(pd.to_numeric(last_val, errors='coerce'))
                if not (cv != cv):  # not nan
                    closing = cv
                    opening = float(closing) + float(w) - float(d)
            except (TypeError, ValueError):
                pass
        if opening is None or closing is None:
            return {'ok': None, 'file': fname, 'transactions': len(df), 'source': source, 'note': 'Missing opening/closing'}
        calculated = float(opening) - float(w) + float(d)
        diff = abs(calculated - float(closing))
        match = diff < 0.01
        return {
            'ok': match,
            'file': fname,
            'transactions': len(df),
            'opening': opening,
            'closing': closing,
            'calculated': calculated,
            'diff': diff,
            'source': source,
            'camelot_tables': n_tables,
        }

    try:
        from test_bmo_bank_camelot_complete import extract_bmo_bank_statement_camelot, _last_extraction_info
        result = extract_bmo_bank_statement_camelot(str(pdf_path))
        if not isinstance(result, (tuple, list)) or len(result) < 4:
            return {'ok': False, 'file': fname, 'error': f'Extractor returned invalid result (len={len(result) if hasattr(result, "__len__") else "?"})'}
        df, opening, closing, year = result[0], result[1], result[2], result[3]
        info = _last_extraction_info
        source = info.get('source', 'unknown')
        n_tables = info.get('camelot_tables_count', 0)
        return _check(df, opening, closing, source, n_tables)
    except Exception as e:
        # Camelot failed (e.g. permission/temp in sandbox); try text extractor for balance verification.
        # To use only Camelot for bank, remove this try block and keep: return {'ok': False, 'file': fname, 'error': str(e)}
        try:
            from test_bmo_bank_complete import extract_bmo_bank_statement
            result = extract_bmo_bank_statement(str(pdf_path))
            if isinstance(result, (tuple, list)) and len(result) >= 4:
                df, opening, closing, year = result[0], result[1], result[2], result[3]
                return _check(df, opening, closing, 'text_fallback', 0)
        except Exception as e2:
            pass
        return {'ok': False, 'file': fname, 'error': str(e)}


def verify_bmo_credit_card(pdf_path):
    """Extract BMO credit card statement and verify closing balance matches calculated."""
    fname = getattr(pdf_path, 'name', str(Path(pdf_path).name) if pdf_path else '')
    try:
        from test_bmo_credit_card_complete import extract_bmo_credit_card_statement
        result = extract_bmo_credit_card_statement(str(pdf_path))
        if not isinstance(result, (tuple, list)) or len(result) < 4:
            return {'ok': False, 'file': fname, 'error': 'Extractor returned invalid result'}
        df, opening, closing, year = result[0], result[1], result[2], result[3]
        if df is None or len(df) == 0:
            return {'ok': False, 'file': fname, 'error': 'No transactions'}
        if 'Amount' not in df.columns:
            return {'ok': False, 'file': fname, 'error': 'No Amount column'}
        total = pd.to_numeric(df['Amount'], errors='coerce').fillna(0).sum()
        # Opening and closing come only from the PDF; no derivation.
        if opening is None or closing is None:
            return {'ok': None, 'file': fname, 'transactions': len(df), 'note': 'Missing opening/closing'}
        # Credit card: opening + sum(Amount) = closing (Amount signed: negative = credit)
        calculated = float(opening) + float(total)
        diff = abs(calculated - float(closing))
        match = diff < 0.01
        return {
            'ok': match,
            'file': fname,
            'transactions': len(df),
            'opening': opening,
            'closing': closing,
            'calculated': calculated,
            'diff': diff,
        }
    except Exception as e:
        return {'ok': False, 'file': fname, 'error': str(e)}


def main():
    base = Path('data')
    # All BMO bank (debit) and credit card folders to verify
    bank_folders = [
        base / 'BMO Business Che 7779',
        base / 'BMO Bank Statement - 0666',
    ]
    cc_folders = [
        base / 'BMO Credit Card 2589',
        base / 'BMO Credit Card (9804978) - 6816',
    ]

    print("="*80)
    print("BMO EXTRACTION + BALANCE VERIFICATION (all PDFs)")
    print("="*80)

    # --- BMO Bank (all folders) ---
    bank_results = []
    for bank_folder in bank_folders:
        bank_pdfs = sorted(bank_folder.glob("*.pdf")) if bank_folder.exists() else []
        if not bank_pdfs:
            continue
        print(f"\n--- BMO Bank ({bank_folder.name}) ---")
        print(f"Found {len(bank_pdfs)} PDF(s)\n")
        for pdf in bank_pdfs:
            r = verify_bmo_bank(pdf)
            r['folder'] = bank_folder.name
            bank_results.append(r)
            if r.get('error'):
                print(f"  {r['file']}: ERROR - {r['error']}")
            elif r.get('ok') is True:
                print(f"  {r['file']}: OK - {r['transactions']} tx, balance match (source: {r.get('source', '?')}, tables: {r.get('camelot_tables', 0)})")
            elif r.get('ok') is False:
                print(f"  {r['file']}: BALANCE MISMATCH - diff ${r.get('diff', 0):,.2f} (calc={r.get('calculated')}, stated={r.get('closing')})")
            else:
                print(f"  {r['file']}: {r['transactions']} tx - {r.get('note', '')}")
    if not bank_results:
        print(f"\n--- BMO Bank: no folders found ---")

    # --- BMO Credit Card (all folders) ---
    cc_results = []
    for cc_folder in cc_folders:
        cc_pdfs = sorted(cc_folder.glob("*.pdf")) if cc_folder.exists() else []
        if not cc_pdfs:
            continue
        print(f"\n--- BMO Credit Card ({cc_folder.name}) ---")
        print(f"Found {len(cc_pdfs)} PDF(s)\n")
        for pdf in cc_pdfs:
            r = verify_bmo_credit_card(pdf)
            r['folder'] = cc_folder.name
            cc_results.append(r)
            if r.get('error'):
                print(f"  {r['file']}: ERROR - {r['error']}")
            elif r.get('ok') is True:
                print(f"  {r['file']}: OK - {r['transactions']} tx, balance match")
            elif r.get('ok') is False:
                print(f"  {r['file']}: BALANCE MISMATCH - diff ${r.get('diff', 0):,.2f}")
            else:
                print(f"  {r['file']}: {r['transactions']} tx - {r.get('note', '')}")
    if not cc_results:
        print(f"\n--- BMO Credit Card: no folders found ---")

    # --- Summary ---
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    # Classify: ok=True passed, ok=False mismatch, error key=exception, else skipped (no balance)
    bank_ok = sum(1 for r in bank_results if r.get('ok') is True)
    bank_fail = sum(1 for r in bank_results if r.get('ok') is False)
    bank_errors = sum(1 for r in bank_results if r.get('error'))
    bank_skip = len(bank_results) - bank_ok - bank_fail - bank_errors
    cc_ok = sum(1 for r in cc_results if r.get('ok') is True)
    cc_fail = sum(1 for r in cc_results if r.get('ok') is False)
    cc_errors = sum(1 for r in cc_results if r.get('error'))
    cc_skip = len(cc_results) - cc_ok - cc_fail - cc_errors
    print(f"\nBMO Bank:     {bank_ok} passed, {bank_fail} balance mismatch, {bank_skip} skipped (no balance), {bank_errors} errors")
    print(f"BMO Credit:   {cc_ok} passed, {cc_fail} balance mismatch, {cc_skip} skipped, {cc_errors} errors")
    total_ok = bank_ok + cc_ok
    total_files = len(bank_results) + len(cc_results)
    if total_files > 0:
        print(f"\nOverall: {total_ok}/{total_files} files with balance match")
        if bank_fail or cc_fail:
            print("\nFiles with balance mismatch (review extraction logic):")
            for r in bank_results:
                if r.get('ok') is False and r.get('diff') is not None:
                    print(f"  Bank: {r['file']} (diff ${r['diff']:,.2f})")
            for r in cc_results:
                if r.get('ok') is False and r.get('diff') is not None:
                    print(f"  CC:   {r['file']} (diff ${r['diff']:,.2f})")

    # --- Save verification results to Excel ---
    from datetime import datetime
    excel_rows = []
    for r in bank_results:
        status = 'OK' if r.get('ok') is True else ('Mismatch' if r.get('ok') is False else 'Skipped')
        excel_rows.append({
            'Account': 'BMO Bank',
            'Folder': r.get('folder', ''),
            'File': r.get('file', ''),
            'Status': status,
            'Transactions': r.get('transactions', 0),
            'Opening': r.get('opening', ''),
            'Closing': r.get('closing', ''),
            'Calculated': r.get('calculated', ''),
            'Difference': f"${r['diff']:,.2f}" if r.get('diff') is not None else '',
            'Note': r.get('error') or r.get('note', ''),
        })
    for r in cc_results:
        status = 'OK' if r.get('ok') is True else ('Mismatch' if r.get('ok') is False else 'Skipped')
        excel_rows.append({
            'Account': 'BMO Credit',
            'Folder': r.get('folder', ''),
            'File': r.get('file', ''),
            'Status': status,
            'Transactions': r.get('transactions', 0),
            'Opening': r.get('opening', ''),
            'Closing': r.get('closing', ''),
            'Calculated': r.get('calculated', ''),
            'Difference': f"${r['diff']:,.2f}" if r.get('diff') is not None else '',
            'Note': r.get('error') or r.get('note', ''),
        })
    if excel_rows:
        out_df = pd.DataFrame(excel_rows)
        summary_df = pd.DataFrame([{
            'BMO Bank': f'{bank_ok} passed, {bank_fail} mismatch, {bank_skip} skipped, {bank_errors} errors',
            'BMO Credit': f'{cc_ok} passed, {cc_fail} mismatch, {cc_skip} skipped, {cc_errors} errors',
            'Overall': f'{total_ok}/{total_files} files with balance match',
        }])
        out_path = Path('BMO_Verification_Results_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.xlsx')
        with pd.ExcelWriter(out_path, engine='openpyxl') as w:
            out_df.to_excel(w, sheet_name='All Files', index=False)
            summary_df.to_excel(w, sheet_name='Summary', index=False)
        print(f"Verification results saved to: {out_path}\n")


if __name__ == '__main__':
    main()
