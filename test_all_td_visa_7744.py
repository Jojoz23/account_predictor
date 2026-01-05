"""Test TD Visa 7744 extraction on all statements"""
import os
import glob
import subprocess
import sys

td_visa_folder = 'data/TD VISA 7744'
pdf_files = glob.glob(os.path.join(td_visa_folder, '*.pdf'))

print("="*80)
print(f"TESTING ALL TD VISA 7744 STATEMENTS ({len(pdf_files)} files)")
print("="*80)

results = []

for pdf_path in sorted(pdf_files):
    print(f"\n{'='*80}")
    print(f"Testing: {os.path.basename(pdf_path)}")
    print('='*80)
    
    try:
        # Run the test script
        result = subprocess.run(
            [sys.executable, 'test_td_visa_complete.py', pdf_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        output = result.stdout + result.stderr
        
        # Extract key information
        opening_balance = None
        closing_balance = None
        total_transactions = None
        running_balance_match = False
        
        for line in output.split('\n'):
            if 'Found opening balance' in line:
                try:
                    opening_balance = float(line.split('$')[1].replace(',', '').split()[0])
                except:
                    pass
            if 'Found closing balance' in line:
                try:
                    closing_balance = float(line.split('$')[1].replace(',', '').split()[0])
                except:
                    pass
            if 'Total transactions:' in line:
                try:
                    total_transactions = int(line.split(':')[1].strip().split()[0])
                except:
                    pass
            if 'Running balance matches' in line or 'OK: Running balance matches' in line:
                running_balance_match = True
        
        results.append({
            'file': os.path.basename(pdf_path),
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
            'total_transactions': total_transactions,
            'running_balance_match': running_balance_match,
            'success': running_balance_match and total_transactions is not None
        })
        
        # Print summary
        if running_balance_match:
            print(f"SUCCESS: {total_transactions} transactions, balance matches")
        else:
            print(f"ISSUES: Check output above")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        results.append({
            'file': os.path.basename(pdf_path),
            'success': False,
            'error': str(e)
        })

# Print final summary
print("\n" + "="*80)
print("FINAL SUMMARY")
print("="*80)
print(f"\nTotal files tested: {len(results)}")
print(f"Successful extractions: {sum(1 for r in results if r.get('success', False))}")
print(f"Failed extractions: {sum(1 for r in results if not r.get('success', False))}")

print("\nDetailed Results:")
print("-" * 80)
for r in results:
    status = "OK" if r.get('success') else "FAIL"
    print(f"{status} {r['file']}")
    if r.get('total_transactions'):
        print(f"   Transactions: {r['total_transactions']}")
    if r.get('opening_balance'):
        print(f"   Opening: ${r['opening_balance']:,.2f}")
    if r.get('closing_balance'):
        print(f"   Closing: ${r['closing_balance']:,.2f}")
    if r.get('running_balance_match'):
        print(f"   Balance Match: OK")
    if r.get('error'):
        print(f"   Error: {r['error']}")
    print()




