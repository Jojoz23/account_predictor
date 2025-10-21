import pdfplumber
import re

pdf_path = "data/1. January 2025 e-statement- bank.pdf"

with pdfplumber.open(pdf_path) as pdf:
    # Get text from page 2 (has mixed transactions)
    page2 = pdf.pages[1]
    text = page2.extract_text()
    
    print("="*70)
    print("SCOTIABANK FORMAT ANALYSIS")
    print("="*70)
    
    # Extract transaction section
    lines = text.split('\n')
    
    print("\nTransaction examples from page 2:")
    print("-"*70)
    
    in_transactions = False
    transaction_count = 0
    
    for i, line in enumerate(lines):
        if 'Date Description Withdrawals/Debits' in line:
            in_transactions = True
            continue
        
        if 'No. of Debits' in line:
            in_transactions = False
            # Show summary
            print(f"\n{line}")
            if i+1 < len(lines):
                print(f"{lines[i+1]}")
            break
        
        if in_transactions and re.match(r'^\d{2}/\d{2}/\d{4}', line):
            print(f"\n{transaction_count+1}. {line}")
            # Show next 3 continuation lines
            for j in range(1, 4):
                if i+j < len(lines) and not re.match(r'^\d{2}/\d{2}/\d{4}', lines[i+j]):
                    print(f"   {lines[i+j]}")
                else:
                    break
            transaction_count += 1
            
            if transaction_count >= 15:  # Show first 15
                break


