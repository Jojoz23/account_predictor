#!/usr/bin/env python3
"""
Convert Excel bank statement files to QuickBooks IIF format
Reads Excel files that have already been processed and creates IIF files
"""

import pandas as pd
import sys
import io
import re
from pathlib import Path
from datetime import datetime

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def excel_to_iif(excel_path, output_path=None, bank_account_name=None, exclude_transfers_to_banks=False, skip_account_definitions=False, 
                 date_from=None, date_to=None, exclude_accounts=None, exclude_description_pattern=None, min_amount=None, max_amount=None):
    """
    Convert Excel file to QuickBooks IIF format
    
    Parameters:
    - excel_path: Path to Excel file
    - output_path: Path for IIF output (default: same name as Excel with .iif extension)
    - bank_account_name: Name of bank account in QuickBooks (default: auto-detect from filename)
    - exclude_transfers_to_banks: If True, exclude transfers to other bank accounts (to avoid duplicates)
                                   Default: False (includes all transactions)
    - skip_account_definitions: If True, skip account definitions section (assumes accounts already exist)
                                Default: False (includes account definitions)
    - date_from: Exclude transactions before this date (YYYY-MM-DD format)
    - date_to: Exclude transactions after this date (YYYY-MM-DD format)
    - exclude_accounts: List of account names to exclude (e.g., ['Sales', 'Income'])
    - exclude_description_pattern: Regex pattern to exclude matching descriptions
    - min_amount: Exclude transactions with absolute amount less than this value
    - max_amount: Exclude transactions with absolute amount greater than this value
    
    Returns:
    - Path to created IIF file, or None if failed
    """
    excel_file = Path(excel_path)
    
    if not excel_file.exists():
        print(f"ERROR: Excel file not found: {excel_path}")
        return None
    
    # Generate output path if not provided
    if output_path is None:
        output_path = excel_file.with_suffix('.iif')
    else:
        output_path = Path(output_path)
    
    # Auto-detect bank account name from filename if not provided
    if bank_account_name is None:
        filename_stem = excel_file.stem  # Gets filename without extension
        # Remove common suffixes that might be added during processing
        filename_stem = filename_stem.replace('_combined', '').replace('_extracted', '').replace('_categorized', '').strip()
        
        # Clean up account name to match QuickBooks format
        # "TD bank - 4738" -> "TD 4738"
        # "BMO Business Che 7779" -> "BMO 7779"
        # Extract bank name and account number
        bank_match = re.match(r'(.+?)\s*(?:bank|business|che|chequing|checking)\s*[-]?\s*(\d+)', filename_stem, re.IGNORECASE)
        if bank_match:
            bank_name = bank_match.group(1).strip()
            account_num = bank_match.group(2).strip()
            bank_account_name = f"{bank_name} {account_num}"
        else:
            bank_account_name = filename_stem
        
        print(f"Reading Excel file: {excel_file.name}")
        print(f"   Auto-detected bank account name: {bank_account_name}")
    else:
        print(f"Reading Excel file: {excel_file.name}")
        print(f"   Using specified bank account name: {bank_account_name}")
    
    try:
        # Read Excel file - try to read the first sheet (usually "Transactions")
        df = pd.read_excel(excel_path, sheet_name=0)
        
        print(f"   Found {len(df)} transactions")
        
        # Check what columns we have
        has_amount = 'Amount' in df.columns
        has_withdrawals = 'Withdrawals' in df.columns
        has_deposits = 'Deposits' in df.columns
        has_account = 'Account' in df.columns
        has_date = 'Date' in df.columns
        has_description = 'Description' in df.columns
        has_running_balance = 'Running_Balance' in df.columns
        
        # Derive opening balance from Excel so QuickBooks ending balance matches statement
        # Running_Balance after first tx = opening + Amount[0], so opening = Running_Balance[0] - Amount[0]
        opening_balance = None
        if has_running_balance and has_amount and len(df) > 0:
            df_sorted = df.dropna(subset=['Date']).copy()
            df_sorted['_date'] = pd.to_datetime(df_sorted['Date'], errors='coerce')
            df_sorted = df_sorted.dropna(subset=['_date']).sort_values('_date')
            if len(df_sorted) > 0 and pd.notna(df_sorted['Running_Balance'].iloc[0]) and pd.notna(df_sorted['Amount'].iloc[0]):
                try:
                    first_rb = float(df_sorted['Running_Balance'].iloc[0])
                    first_amt = float(df_sorted['Amount'].iloc[0])
                    opening_balance = first_rb - first_amt
                    if abs(opening_balance) < 1e-6:
                        opening_balance = None
                    else:
                        print(f"   Opening balance (from Running_Balance): {opening_balance:,.2f}")
                except (TypeError, ValueError):
                    pass
        
        if not has_date or not has_description:
            print("❌ Excel file must have 'Date' and 'Description' columns")
            return None
        
        # Helper function to clean account names (define before use)
        def clean_account_name(account_name):
            """Clean account name to match QuickBooks format"""
            # Clean bank account names: "TD bank - 4738" -> "TD 4738"
            bank_match = re.match(r'(.+?)\s*(?:bank|business|che|chequing|checking)\s*[-]?\s*(\d+)', account_name, re.IGNORECASE)
            if bank_match:
                bank_name = bank_match.group(1).strip()
                account_num = bank_match.group(2).strip()
                return f"{bank_name} {account_num}"
            return account_name
        
        # Helper function to check if account is a bank account
        def is_bank_account(acc_name):
            """Check if account name represents a bank account"""
            if not acc_name:
                return False
            acc_lower = acc_name.lower()
            # Check for bank keywords
            if 'bank' in acc_lower or 'checking' in acc_lower or 'chequing' in acc_lower:
                return True
            # Check for bank account pattern (e.g., "TD 4738", "BMO 7206")
            bank_pattern = re.match(r'^([A-Z]{2,})\s+(\d+)$', acc_name)
            if bank_pattern:
                bank_code = bank_pattern.group(1).upper()
                if bank_code in ['TD', 'BMO', 'RBC', 'CIBC', 'SCOTIA', 'SCOTIABANK', 'TANGERINE', 'NB', 'NATIONAL']:
                    return True
            return False
        
        # Collect all unique accounts first
        unique_accounts = set()
        unique_accounts.add(bank_account_name)  # Add bank account
        
        # Process transactions and collect accounts
        transaction_data = []
        transaction_count = 0
        
        for idx, row in df.iterrows():
            try:
                # Parse date
                if pd.isna(row['Date']):
                    continue
                    
                date_val = pd.to_datetime(row['Date'], errors='coerce')
                if pd.isna(date_val):
                    continue
                
                # Date filtering
                if date_from:
                    from_date = pd.to_datetime(date_from)
                    if date_val < from_date:
                        continue
                if date_to:
                    to_date = pd.to_datetime(date_to)
                    if date_val > to_date:
                        continue
                
                date_str = date_val.strftime('%m/%d/%Y')
                
                # Get description
                description = str(row['Description'])[:100] if not pd.isna(row['Description']) else ""
                
                # Description pattern filtering
                if exclude_description_pattern:
                    if re.search(exclude_description_pattern, description, re.IGNORECASE):
                        continue
                
                # Determine transaction type and amount
                amount = None
                trns_type = None
                account = None
                
                if has_amount:
                    # Credit card format - single Amount column
                    # Positive Amount = purchase/charge → TRNSTYPE "CREDIT CARD" (TRNS -amt, SPL +amt)
                    # Negative Amount = payment or refund → TRNSTYPE "CCARD REFUND" (TRNS +amt, SPL -amt)
                    if pd.isna(row['Amount']):
                        continue
                    amount = float(row['Amount'])
                    if amount == 0:
                        continue
                    if amount > 0:
                        trns_type = "CREDIT CARD"
                    else:
                        trns_type = "CCARD REFUND"
                    account = str(row['Account']) if has_account and not pd.isna(row.get('Account')) else "Sales"
                    
                elif has_withdrawals or has_deposits:
                    # Bank account format - separate Withdrawals/Deposits columns
                    withdrawal = float(row['Withdrawals']) if has_withdrawals and not pd.isna(row.get('Withdrawals')) else 0.0
                    deposit = float(row['Deposits']) if has_deposits and not pd.isna(row.get('Deposits')) else 0.0
                    
                    if withdrawal > 0:
                        amount = -withdrawal  # Negative for withdrawals
                        trns_type = "CHEQUE"  # Use CHEQUE for withdrawals
                        account = str(row['Account']) if has_account and not pd.isna(row.get('Account')) else "Sales"
                    elif deposit > 0:
                        amount = deposit  # Positive for deposits
                        trns_type = "DEPOSIT"
                        account = str(row['Account']) if has_account and not pd.isna(row.get('Account')) else "Sales"
                    else:
                        continue  # Skip transactions with no amount
                else:
                    print("ERROR: Excel file must have either 'Amount' column or 'Withdrawals'/'Deposits' columns")
                    return None
                
                if amount == 0:
                    continue
                
                # Amount filtering
                abs_amount = abs(amount)
                if min_amount is not None and abs_amount < min_amount:
                    continue
                if max_amount is not None and abs_amount > max_amount:
                    continue
                
                # Default account if missing
                if not account or account == 'nan':
                    account = "Sales"
                
                # Account filtering (check before processing further)
                if exclude_accounts:
                    cleaned_account = clean_account_name(account)
                    if account in exclude_accounts or cleaned_account in exclude_accounts:
                        continue
                
                # Exclude transfers to other bank accounts if requested (to avoid duplicates)
                if exclude_transfers_to_banks:
                    # Check if this is a transfer to another bank account
                    cleaned_account = clean_account_name(account)
                    cleaned_bank_account = clean_account_name(bank_account_name)
                    if is_bank_account(cleaned_account) and cleaned_account != cleaned_bank_account:
                        # This is a transfer to another bank account - skip it to avoid duplicates
                        # (it will be imported from the other account's statement as a deposit)
                        continue
                
                # Add accounts to set
                unique_accounts.add(account)
                
                # Store transaction data
                transaction_data.append({
                    'date_str': date_str,
                    'description': description,
                    'amount': amount,
                    'trns_type': trns_type,
                    'account': account
                })
                
            except Exception as e:
                print(f"WARNING: Error processing row {idx}: {e}")
                continue
        
        # If we have opening balance, we need Opening Bal Equity account for the opening-balance transaction
        if opening_balance is not None:
            unique_accounts.add("Opening Bal Equity")
        
        # Prepare IIF content
        iif_content = []
        
        # Account type mapping - map account names to QuickBooks account types
        # QuickBooks uses abbreviated codes: BANK, CCARD, INC, EXP, etc.
        def get_account_type(account_name):
            """Determine QuickBooks account type based on account name"""
            account_lower = account_name.lower()
            
            # Bank accounts - check for bank patterns or account numbers (like "TD 4738", "BMO 7779")
            if 'bank' in account_lower or 'checking' in account_lower or 'chequing' in account_lower or 'savings' in account_lower:
                return "BANK"
            # Check if it's a bank account by pattern (e.g., "TD 4738", "BMO 7206")
            bank_pattern = re.match(r'^([A-Z]{2,})\s+(\d+)$', account_name)
            if bank_pattern:
                bank_code = bank_pattern.group(1).upper()
                # Common bank codes
                if bank_code in ['TD', 'BMO', 'RBC', 'CIBC', 'SCOTIA', 'SCOTIABANK', 'TANGERINE', 'NB', 'NATIONAL']:
                    return "BANK"
            # Credit cards
            if 'visa' in account_lower or 'mastercard' in account_lower or 'credit card' in account_lower or 'amex' in account_lower:
                return "CCARD"
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
            # Opening balance equity (QuickBooks standard)
            if 'opening bal' in account_lower and 'equity' in account_lower:
                return "EQUITY"
            # Default to expense for unknown accounts
            return "EXP"
        
        # Helper function to clean account names
        def clean_account_name(account_name):
            """Clean account name to match QuickBooks format"""
            # Clean bank account names: "TD bank - 4738" -> "TD 4738"
            bank_match = re.match(r'(.+?)\s*(?:bank|business|che|chequing|checking)\s*[-]?\s*(\d+)', account_name, re.IGNORECASE)
            if bank_match:
                bank_name = bank_match.group(1).strip()
                account_num = bank_match.group(2).strip()
                return f"{bank_name} {account_num}"
            return account_name
        
        # Add account list definitions using correct format: !ACCNT header
        # Format: !ACCNT    NAME    ACCNTTYPE    DESC (note: ACCNTTYPE with double T)
        # Skip if user wants to assume accounts already exist
        if not skip_account_definitions:
            iif_content.append("!ACCNT\tNAME\tACCNTTYPE\tDESC")
            for account_name in sorted(unique_accounts):
                # Clean account name first
                cleaned_name = clean_account_name(account_name)
                # Determine account type based on original name (before cleaning)
                account_type = get_account_type(account_name)
                # If cleaned name is different, re-check type
                if cleaned_name != account_name:
                    account_type = get_account_type(cleaned_name)
                # Use ACCNT (not ACNT) for data rows
                iif_content.append(f"ACCNT\t{cleaned_name}\t{account_type}\t")
            
            # Add blank line before transactions
            iif_content.append("")
        
        # Transaction headers
        iif_content.append("!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tMEMO")
        iif_content.append("!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tMEMO")
        iif_content.append("!ENDTRNS")
        
        # Clean bank account name for transactions (function already defined above)
        cleaned_bank_account = clean_account_name(bank_account_name)
        main_account_type = get_account_type(bank_account_name)
        
        # Process transactions
        transaction_count = 0
        
        # Add opening balance transaction so QuickBooks ending balance matches statement
        if opening_balance is not None and main_account_type in ("CCARD", "BANK"):
            ob_date = transaction_data[0]["date_str"] if transaction_data else (
                pd.to_datetime(df["Date"].min(), errors="coerce").strftime("%m/%d/%Y")
                if has_date and len(df) else "01/01/2025"
            )
            if main_account_type == "CCARD":
                ob_trns_type = "CREDIT CARD"
                trns_amt = opening_balance  # negative = owed
                spl_amt = -opening_balance
            else:
                ob_trns_type = "DEPOSIT" if opening_balance > 0 else "CHECK"
                trns_amt = opening_balance
                spl_amt = -opening_balance
            iif_content.append(f"TRNS\t{transaction_count}\t{ob_trns_type}\t{ob_date}\t{cleaned_bank_account}\t\t\t{trns_amt:.2f}\t\tOpening balance")
            iif_content.append(f"SPL\t{transaction_count}\t{ob_trns_type}\t{ob_date}\tOpening Bal Equity\t\t\t{spl_amt:.2f}\t\tOpening balance")
            iif_content.append("ENDTRNS")
            transaction_count += 1
        
        for tx in transaction_data:
            # Clean account name for transaction
            cleaned_account = clean_account_name(tx['account'])
            amt = tx['amount']
            
            # Credit card: IIF kit uses CREDIT CARD (charge) and CCARD REFUND (payment/refund)
            # CREDIT CARD:  TRNS = -amount, SPL = +amount  (charge on card, expense)
            # CCARD REFUND: TRNS = +|amount|, SPL = -|amount|  (credit to card, e.g. payment or refund)
            if tx['trns_type'] == "CREDIT CARD":
                trns_amt = -amt
                spl_amt = amt
            elif tx['trns_type'] == "CCARD REFUND":
                abs_amt = abs(amt)
                trns_amt = abs_amt
                spl_amt = -abs_amt
            else:
                trns_amt = amt
                spl_amt = -amt
            
            # Create transaction entry
            # TRNS row: source account side
            iif_content.append(f"TRNS\t{transaction_count}\t{tx['trns_type']}\t{tx['date_str']}\t{cleaned_bank_account}\t\t\t{trns_amt:.2f}\t\t{tx['description']}")
            
            # SPL row: category account side
            iif_content.append(f"SPL\t{transaction_count}\t{tx['trns_type']}\t{tx['date_str']}\t{cleaned_account}\t\t\t{spl_amt:.2f}\t\t{tx['description']}")
            
            # End transaction
            iif_content.append("ENDTRNS")
            
            transaction_count += 1
        
        # Write IIF file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(iif_content))
        
        print(f"✅ IIF file created: {output_path}")
        print(f"   Transactions exported: {transaction_count}")
        print(f"   Import this file into QuickBooks Desktop: File → Utilities → Import → Import IIF")
        
        return output_path
        
    except Exception as e:
        print(f"ERROR: Error reading Excel file: {e}")
        import traceback
        traceback.print_exc()
        return None


def batch_convert_folder(folder_path, output_folder=None, bank_account_name="Checking Account", exclude_transfers_to_banks=True, skip_account_definitions=False):
    """
    Convert all Excel files in a folder to IIF format
    
    Parameters:
    - folder_path: Path to folder containing Excel files
    - output_folder: Folder to save IIF files (default: same as Excel files)
    - bank_account_name: Name of bank account in QuickBooks
    """
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder not found: {folder_path}")
        return
    
    excel_files = list(folder.glob("*.xlsx"))
    
    if not excel_files:
        print(f"ERROR: No Excel files found in: {folder_path}")
        return
    
    print("="*80)
    print(f"BATCH CONVERTING EXCEL FILES TO IIF FORMAT")
    print("="*80)
    print(f"Folder: {folder_path}")
    print(f"Found {len(excel_files)} Excel file(s)\n")
    
    if output_folder:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    for excel_file in excel_files:
        print(f"\n{'='*80}")
        if output_folder:
            output_path = output_folder / excel_file.with_suffix('.iif').name
        else:
            output_path = None
        
        result = excel_to_iif(excel_file, output_path, bank_account_name, exclude_transfers_to_banks=exclude_transfers_to_banks, skip_account_definitions=skip_account_definitions)
        if result:
            success_count += 1
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: {success_count}/{len(excel_files)} files converted successfully")
    print("="*80)


def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert Excel bank statement files to QuickBooks IIF format'
    )
    parser.add_argument('input', help='Excel file or folder containing Excel files')
    parser.add_argument('-o', '--output', help='Output file or folder path')
    parser.add_argument('-a', '--account', default=None,
                       help='Bank account name in QuickBooks (default: auto-detect from filename)')
    parser.add_argument('--exclude-transfers', action='store_true',
                       help='Exclude transfers to other bank accounts to avoid duplicates (default: include all transactions)')
    parser.add_argument('--skip-accounts', action='store_true',
                       help='Skip account definitions in IIF file (assumes accounts already exist in QuickBooks)')
    parser.add_argument('--date-from', type=str,
                       help='Exclude transactions before this date (YYYY-MM-DD format)')
    parser.add_argument('--date-to', type=str,
                       help='Exclude transactions after this date (YYYY-MM-DD format)')
    parser.add_argument('--exclude-account', action='append', dest='exclude_accounts',
                       help='Exclude transactions with this account (can be used multiple times)')
    parser.add_argument('--exclude-description', type=str,
                       help='Exclude transactions matching this regex pattern in description')
    parser.add_argument('--min-amount', type=float,
                       help='Exclude transactions with absolute amount less than this value')
    parser.add_argument('--max-amount', type=float,
                       help='Exclude transactions with absolute amount greater than this value')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    exclude_transfers = args.exclude_transfers  # Default: include all transactions
    
    if input_path.is_file():
        # Single file
        excel_to_iif(input_path, args.output, args.account, 
                    exclude_transfers_to_banks=exclude_transfers, 
                    skip_account_definitions=args.skip_accounts,
                    date_from=args.date_from,
                    date_to=args.date_to,
                    exclude_accounts=args.exclude_accounts,
                    exclude_description_pattern=args.exclude_description,
                    min_amount=args.min_amount,
                    max_amount=args.max_amount)
    elif input_path.is_dir():
        # Folder
        batch_convert_folder(input_path, args.output, args.account, 
                           exclude_transfers_to_banks=exclude_transfers, 
                           skip_account_definitions=args.skip_accounts)
    else:
        print(f"ERROR: Path not found: {input_path}")


if __name__ == '__main__':
    main()
