#!/usr/bin/env python3
"""
Create a separate IIF file with account definitions
This file should be imported BEFORE importing transactions
"""

import pandas as pd
import sys
import io
import re
from pathlib import Path

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def create_accounts_iif(excel_path, output_path=None):
    """
    Create an IIF file with account definitions from Excel file
    
    Parameters:
    - excel_path: Path to Excel file
    - output_path: Path for IIF output (default: accounts_[excel_name].iif)
    """
    excel_file = Path(excel_path)
    
    if not excel_file.exists():
        print(f"ERROR: Excel file not found: {excel_path}")
        return None
    
    # Generate output path if not provided
    if output_path is None:
        output_path = excel_file.parent / f"accounts_{excel_file.stem}.iif"
    else:
        output_path = Path(output_path)
    
    print(f"Reading Excel file: {excel_file.name}")
    
    try:
        # Read Excel file
        df = pd.read_excel(excel_path, sheet_name=0)
        
        # Collect all unique accounts
        unique_accounts = set()
        
        # Check what columns we have
        has_amount = 'Amount' in df.columns
        has_withdrawals = 'Withdrawals' in df.columns
        has_deposits = 'Deposits' in df.columns
        has_account = 'Account' in df.columns
        
        # Get bank account name from filename
        filename_stem = excel_file.stem
        filename_stem = filename_stem.replace('_combined', '').replace('_extracted', '').replace('_categorized', '').strip()
        bank_match = re.match(r'(.+?)\s*(?:bank|business|che|chequing|checking)\s*[-]?\s*(\d+)', filename_stem, re.IGNORECASE)
        if bank_match:
            bank_name = bank_match.group(1).strip()
            account_num = bank_match.group(2).strip()
            bank_account_name = f"{bank_name} {account_num}"
        else:
            bank_account_name = filename_stem
        
        unique_accounts.add(bank_account_name)
        
        # Collect accounts from transactions
        for idx, row in df.iterrows():
            if has_account and not pd.isna(row.get('Account')):
                account = str(row['Account']).strip()
                if account and account != 'nan':
                    unique_accounts.add(account)
            else:
                # Add default account
                unique_accounts.add("Sales")
        
        # Account type mapping
        def get_account_type(account_name):
            """Determine QuickBooks account type based on account name"""
            account_lower = account_name.lower()
            
            # Bank accounts
            if 'bank' in account_lower or 'checking' in account_lower or 'chequing' in account_lower or 'savings' in account_lower:
                return "BANK"
            # Check bank account pattern (e.g., "TD 4738")
            bank_pattern = re.match(r'^([A-Z]{2,})\s+(\d+)$', account_name)
            if bank_pattern:
                bank_code = bank_pattern.group(1).upper()
                if bank_code in ['TD', 'BMO', 'RBC', 'CIBC', 'SCOTIA', 'SCOTIABANK', 'TANGERINE', 'NB', 'NATIONAL']:
                    return "BANK"
            # Credit cards
            if 'visa' in account_lower or 'mastercard' in account_lower or 'credit card' in account_lower or 'amex' in account_lower:
                return "CREDIT CARD"
            # Income accounts
            if 'sales' in account_lower or 'income' in account_lower or 'revenue' in account_lower:
                return "INC"
            # Expense accounts
            if 'expense' in account_lower or 'charges' in account_lower or 'fee' in account_lower:
                return "EXP"
            # Cash
            if 'cash' in account_lower:
                return "BANK"
            # Salary/Payroll
            if 'salary' in account_lower or 'payroll' in account_lower or 'wages' in account_lower:
                return "EXP"
            # Transfer accounts
            if 'transfer' in account_lower:
                return "BANK"
            # Default to expense
            return "EXP"
        
        # Create IIF content - try using !ACCTLIST format
        iif_content = []
        
        # Try different account list formats
        # Format 1: Simple account list (may not work, but worth trying)
        iif_content.append("!ACCTLIST")
        iif_content.append("ACCTLIST")
        
        for account_name in sorted(unique_accounts):
            account_type = get_account_type(account_name)
            # Try format: NAME, TYPE
            iif_content.append(f"{account_name}\t{account_type}")
        
        # Write IIF file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(iif_content))
        
        print(f"SUCCESS: Account list file created: {output_path}")
        print(f"   Accounts defined: {len(unique_accounts)}")
        print(f"\nNOTE: This format may not work. If it doesn't, you'll need to:")
        print(f"   1. Create accounts manually in QuickBooks first, OR")
        print(f"   2. Export your chart of accounts from QuickBooks to see the correct format")
        
        return output_path
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python create_accounts_iif.py <excel_file>")
        sys.exit(1)
    
    create_accounts_iif(sys.argv[1])
