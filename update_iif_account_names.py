#!/usr/bin/env python3
"""
Update account names in an existing IIF file using a mapping CSV.
Use this after generating the IIF from Excel so account names match your
QuickBooks chart of accounts (avoids duplicate accounts).

When Accounts.TXT (QB chart of accounts export) is present, ACCNT types in the IIF
are set from it so QuickBooks won't try to change account types on import (avoids error 3210).

Mapping CSV must have columns: StatementAccount, QBAccount

Usage:
  python update_iif_account_names.py "path/to/file.iif"
  python update_iif_account_names.py "path/to/file.iif" -m account_names_map.csv
  python update_iif_account_names.py "path/to/file.iif" -a Accounts.TXT -o "path/to/updated.iif"
"""

import csv
from pathlib import Path

# QuickBooks export "Type" -> IIF ACCNTTYPE code (so we don't overwrite QB's types)
QB_TYPE_TO_IIF = {
    "Bank": "BANK",
    "Credit Card": "CCARD",
    "Accounts Receivable": "AR",
    "Other Current Asset": "OCASSET",
    "Fixed Asset": "FIXASSET",
    "Other Asset": "OASSET",
    "Accounts Payable": "AP",
    "Other Current Liability": "OCLIAB",
    "Long Term Liability": "LTLIAB",
    "Equity": "EQUITY",
    "Income": "INC",
    "Cost of Goods Sold": "COGS",
    "Expense": "EXP",
    "Other Expense": "EXEXP",
    "Other Income": "EXINC",
    "Non-Posting": "NONPOSTING",
}

def load_account_types_txt(txt_path):
    """Parse Accounts.TXT (QB chart export). Returns dict: account name -> IIF type code."""
    path = Path(txt_path)
    if not path.exists():
        return {}
    # Match type from end of line (longest first so "Other Current Liability" before "Liability")
    qb_types_sorted = sorted(QB_TYPE_TO_IIF.keys(), key=len, reverse=True)
    result = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or 'Chart of Accounts' in line or line == 'Type' or (line.startswith('Account') and 'Type' in line):
                continue
            if line == 'Page 1':
                break
            for qb_type in qb_types_sorted:
                if line.endswith(qb_type):
                    name = line[:-len(qb_type)].strip()
                    if name:
                        result[name] = QB_TYPE_TO_IIF[qb_type]
                    break
    return result

def load_account_map(map_path):
    """Load CSV with StatementAccount, QBAccount. Returns dict: lowercase statement name -> QB name."""
    mapping = {}
    with open(map_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if 'StatementAccount' not in reader.fieldnames or 'QBAccount' not in reader.fieldnames:
            print("ERROR: Mapping CSV must have columns StatementAccount and QBAccount")
            return None
        for row in reader:
            k = (row.get('StatementAccount') or '').strip().lower()
            v = (row.get('QBAccount') or '').strip()
            if k and v:
                mapping[k] = v
    return mapping

def update_iif_account_names(iif_path, map_path=None, output_path=None, accounts_txt_path=None):
    """
    Read IIF, replace account names using the mapping, write back (or to output_path).
    If accounts_txt_path (Accounts.TXT) is given, ACCNT types are set from it so QB won't change types.
    - ACCNT data rows: account name is column index 1, type column index 2
    - TRNS rows: account name is column index 4
    - SPL rows: account name is column index 4
    """
    iif_path = Path(iif_path)
    if not iif_path.exists():
        print(f"ERROR: IIF file not found: {iif_path}")
        return None

    script_dir = Path(__file__).resolve().parent
    if map_path is None:
        map_path = script_dir / "account_names_map.csv"
        if not map_path.exists():
            map_path = script_dir / "config" / "account_names_map.csv"
    else:
        map_path = Path(map_path)
    if not map_path.exists():
        print(f"ERROR: Mapping file not found: {map_path}")
        return None

    mapping = load_account_map(map_path)
    if mapping is None:
        return None
    print(f"Loaded {len(mapping)} account name mappings from {map_path.name}")

    if accounts_txt_path is None:
        accounts_txt_path = script_dir / "Accounts.TXT"
        if not accounts_txt_path.exists():
            accounts_txt_path = script_dir / "config" / "Accounts.TXT"
    else:
        accounts_txt_path = Path(accounts_txt_path)
    account_types = load_account_types_txt(accounts_txt_path)
    if account_types:
        print(f"Loaded {len(account_types)} account types from {accounts_txt_path.name} (will preserve QB types in ACCNT)")

    if output_path is None:
        output_path = iif_path
    else:
        output_path = Path(output_path)

    with open(iif_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    out_lines = []
    replacements = 0
    for line in lines:
        if not line.strip():
            out_lines.append(line)
            continue
        parts = line.rstrip('\n').split('\t')
        # ACCNT data row (not header !ACCNT): replace column 1 (name), set type from Accounts.TXT when present
        if len(parts) >= 3 and parts[0] == 'ACCNT' and not line.startswith('!'):
            name = parts[1].strip()
            key = name.lower()
            if key in mapping:
                parts[1] = mapping[key]
                replacements += 1
            # Use type from Accounts.TXT so we don't overwrite QB account types (avoids error 3210)
            resolved_name = parts[1].strip()
            if resolved_name in account_types:
                parts[2] = account_types[resolved_name]
            elif not account_types:
                # No Accounts.TXT: still fix known credit card accounts so import doesn't fail with 3140
                if resolved_name in {"BMO World Elite Mastercard 2589", "Scotia Visa", "Opening Balance in Credit card"}:
                    parts[2] = "CCARD"
        # TRNS row: replace column 4 (ACCNT)
        elif len(parts) >= 5 and parts[0] == 'TRNS':
            name = parts[4].strip()
            key = name.lower()
            if key in mapping:
                parts[4] = mapping[key]
                replacements += 1
        # SPL row: replace column 4 (ACCNT)
        elif len(parts) >= 5 and parts[0] == 'SPL':
            name = parts[4].strip()
            key = name.lower()
            if key in mapping:
                parts[4] = mapping[key]
                replacements += 1
        out_lines.append('\t'.join(parts) + '\n')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

    print(f"Updated {replacements} account name(s) in {output_path}")
    return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Update account names in an IIF file using a mapping CSV')
    parser.add_argument('iif_file', help='Path to the IIF file')
    parser.add_argument('-m', '--map', default=None, help='Path to mapping CSV (default: account_names_map.csv in script folder)')
    parser.add_argument('-a', '--accounts', default=None, help='Path to Accounts.TXT from QB (default: Accounts.TXT in script folder); used to set ACCNT types so QB does not change them')
    parser.add_argument('-o', '--output', default=None, help='Output IIF path (default: overwrite input file)')
    args = parser.parse_args()
    update_iif_account_names(args.iif_file, args.map, args.output, args.accounts)

if __name__ == '__main__':
    main()
