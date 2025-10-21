import pdfplumber
import pandas as pd
import re

pdf_path = "data/1. January 2025 e-statement- bank.pdf"

print("="*70)
print("COMPREHENSIVE TEXT-BASED EXTRACTION")
print("="*70)

transactions = []

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, 1):
        text = page.extract_text()
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Match transaction line: MM/DD/YYYY DESCRIPTION AMOUNT BALANCE
            # The tricky part: AMOUNT could be in withdrawal OR deposit position
            # Format: DATE DESC [WITHDRAWAL] [DEPOSIT] BALANCE
            
            match = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.+)$', line)
            
            if match:
                date_str = match.group(1)
                rest = match.group(2).strip()
                
                # Collect description from this line and continuation lines
                desc_parts = []
                
                # Extract all numbers from the first line
                # Pattern matches: 123, 1,234, 123.45, 123.45-, 1,234.56-
                num_pattern = r'[\d,]+(?:\.\d{1,2})?-?'
                numbers = re.findall(num_pattern, rest)
                
                # Remove numbers from line to get description
                desc_first = re.sub(num_pattern, '', rest).strip()
                if desc_first:
                    desc_parts.append(desc_first)
                
                # Get continuation lines (no date prefix)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    
                    # Stop conditions
                    if not next_line:
                        j += 1
                        continue
                    if re.match(r'^\d{2}/\d{2}/\d{4}', next_line):
                        break
                    if any(keyword in next_line for keyword in ['No. of Debits', 'Total', 'Statement Of', 'Account Number']):
                        break
                    
                    # Add continuation line to description
                    desc_parts.append(next_line)
                    j += 1
                
                full_desc = ' '.join(desc_parts)
                
                # Parse amounts
                # Last number is balance, others are transaction amounts
                if len(numbers) >= 1:
                    balance = numbers[-1]
                    
                    # Determine withdrawal vs deposit
                    withdrawal = None
                    deposit = None
                    
                    if len(numbers) == 2:
                        # One amount + balance
                        amount = numbers[0]
                        
                        # Use description to determine type
                        if 'DEPOSIT' in full_desc.upper():
                            deposit = amount
                        else:
                            # Check if it's a credit-type transaction
                            credit_types = ['HEALTH/DENTAL CLAIM', 'MISC PAYMENT', 'BUSINESS PAD', 'ONTARIO DRUG BENEFIT']
                            if any(keyword in full_desc.upper() for keyword in credit_types):
                                deposit = amount
                            else:
                                withdrawal = amount
                    
                    elif len(numbers) >= 3:
                        # Two amounts + balance
                        # First is withdrawal, second is deposit
                        withdrawal = numbers[0] if numbers[0] else None
                        deposit = numbers[1] if numbers[1] else None
                    
                    # Only add if we have a real description
                    if full_desc and 'BALANCE FORWARD' not in full_desc.upper():
                        transactions.append({
                            'Date': date_str,
                            'Description': full_desc,
                            'Withdrawals': withdrawal,
                            'Deposits': deposit,
                            'Balance': balance
                        })
                
                i = j
            else:
                i += 1

df = pd.DataFrame(transactions)

print(f"\nExtracted: {len(df)} transactions")
print(f"\nBreakdown:")
print(f"  Withdrawals: {df['Withdrawals'].notna().sum()}")
print(f"  Deposits: {df['Deposits'].notna().sum()}")
print(f"\nExpected: 36 debits + 98 credits = 134 total")
print(f"\nSample:")
print(df[['Date', 'Description', 'Withdrawals', 'Deposits']].head(10).to_string(index=False))



