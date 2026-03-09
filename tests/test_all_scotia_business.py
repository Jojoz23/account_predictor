"""Test extraction on all Scotiabank Business PDFs and generate Excel files"""
import os
import sys
from extract_bank_statements import BankStatementExtractor

scotia_folder = 'data/Scotia Business'

print("="*80)
print("TESTING ALL SCOTIABANK BUSINESS STATEMENTS")
print("="*80)

pdf_files = [f for f in os.listdir(scotia_folder) if f.lower().endswith('.pdf')]
pdf_files.sort()

print(f"\nFound {len(pdf_files)} PDF files:")
for pdf in pdf_files:
    print(f"  - {pdf}")

results = []

for pdf_file in pdf_files:
    pdf_path = os.path.join(scotia_folder, pdf_file)
    print(f"\n{'='*80}")
    print(f"Processing: {pdf_file}")
    print(f"{'='*80}")
    
    try:
        extractor = BankStatementExtractor(pdf_path)
        df = extractor.extract(strategy='camelot')
        
        if df is not None and len(df) > 0:
            # Generate Excel filename
            excel_filename = pdf_file.replace('.pdf', '.xlsx')
            excel_path = os.path.join(scotia_folder, excel_filename)
            
            # Save to Excel
            extractor.save_to_excel(df, excel_path)
            
            # Get metadata
            opening = extractor.metadata.get('opening_balance')
            closing = extractor.metadata.get('closing_balance')
            running_balance = df['Running_Balance'].iloc[-1] if 'Running_Balance' in df.columns else None
            
            results.append({
                'file': pdf_file,
                'transactions': len(df),
                'opening_balance': opening,
                'closing_balance': closing,
                'final_running_balance': running_balance,
                'excel_file': excel_filename,
                'status': 'SUCCESS'
            })
            
            print(f"✅ Extracted {len(df)} transactions")
            print(f"✅ Saved to: {excel_filename}")
            if opening is not None:
                print(f"   Opening: ${opening:,.2f}")
            if closing is not None:
                print(f"   Closing: ${closing:,.2f}")
            if running_balance is not None:
                print(f"   Final Running: ${running_balance:,.2f}")
        else:
            results.append({
                'file': pdf_file,
                'transactions': 0,
                'status': 'FAILED - No transactions extracted'
            })
            print(f"❌ No transactions extracted")
    except Exception as e:
        results.append({
            'file': pdf_file,
            'transactions': 0,
            'status': f'ERROR: {str(e)}'
        })
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

# Summary
print(f"\n\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"{'File':<30} {'Transactions':<15} {'Status':<30}")
print("-"*80)
for r in results:
    status = r.get('status', 'SUCCESS')
    txn_count = r.get('transactions', 0)
    print(f"{r['file']:<30} {txn_count:<15} {status:<30}")

print(f"\n✅ Excel files saved in: {scotia_folder}")

