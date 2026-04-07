#!/usr/bin/env python3
"""
Adjust IIF so that H-coded expenses do NOT have explicit GST/HST Payable splits.

For each transaction where:
  - There is a SPL line to one of the H_ACCOUNTS (e.g. Telephone Expense)
  - AND a SPL line to GST/HST Payable

We:
  - Keep the TRNS amount as-is (gross cheque amount)
  - Replace the H-account SPL amount with gross/1.13 (net)
  - Remove the GST/HST Payable SPL line(s)

QuickBooks will then compute GST from the H tax code on the expense account,
so the cheque total remains correct without double-taxing.

Usage (from repo root):

  .venv\\Scripts\\python.exe tools\\adjust_h_accounts_iif.py \\
      \"data\\iif\\114 - lovely\\TD Bank - 5931_with_gst_final.iif\" \\
      \"data\\iif\\114 - lovely\\TD Bank - 5931_Htax_net.iif\"
"""

from pathlib import Path
import sys


DEFAULT_H_ACCOUNTS = {
    "Office Supplies",
    "Repairs and Maintenance",
    "Telephone Expense",
    "Utilities",
    "Automobile Expense",
    "Computer and Internet Expenses",
    "Meals and Entertainment",
    "Advertising and Promotion",
}

GST_ACCOUNT_NAME = "GST/HST Payable"
H_RATE = 1.13  # 13% HST


def parse_amount(text: str) -> float:
    try:
        return float(text)
    except Exception:
        return 0.0


def load_h_accounts(config_path: str | None = None) -> set[str]:
    """Load H-coded accounts from config file, with safe fallback."""
    if config_path:
        path = Path(config_path)
    else:
        repo_root = Path(__file__).resolve().parent.parent
        path = repo_root / "config" / "h_accounts.txt"

    if not path.exists():
        print(f"WARNING: H accounts config not found at {path}, using defaults.")
        return set(DEFAULT_H_ACCOUNTS)

    accounts: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        accounts.add(name)

    if not accounts:
        print(f"WARNING: No H accounts found in {path}, using defaults.")
        return set(DEFAULT_H_ACCOUNTS)

    print(f"Loaded {len(accounts)} H account(s) from {path}")
    return accounts


def adjust_file(input_path: str, output_path: str, h_accounts: set[str]) -> None:
    src = Path(input_path)
    dst = Path(output_path)

    if not src.exists():
        print(f"❌ Input IIF not found: {src}")
        return

    lines = src.read_text(encoding="utf-8").splitlines()

    # Copy header (ACCNT section + !TRNS/!SPL/!ENDTRNS header block)
    header = []
    idx = 0
    while idx < len(lines):
        header.append(lines[idx])
        if lines[idx].startswith("!ENDTRNS"):
            idx += 1
            break
        idx += 1

    # Group TRNS/SPL/ENDTRNS blocks
    groups = []
    cur = []
    for line in lines[idx:]:
        if line.startswith("TRNS\t"):
            if cur:
                groups.append(cur)
                cur = []
            cur.append(line)
        elif line.startswith("SPL\t") or line.startswith("ENDTRNS"):
            cur.append(line)
            if line.startswith("ENDTRNS"):
                groups.append(cur)
                cur = []
    if cur:
        groups.append(cur)

    adjusted_groups: list[list[str]] = []
    adjusted_count = 0

    for grp in groups:
        # Parse TRNS amount once for this group (gross cheque/deposit amount)
        trns_line = grp[0]
        trns_parts = trns_line.split("\t")
        trns_amt = parse_amount(trns_parts[7]) if len(trns_parts) > 7 else 0.0
        gross = abs(trns_amt)

        # Find SPL lines for H accounts and GST/HST Payable
        h_spl_indices = []
        gst_spl_indices = []
        for i, line in enumerate(grp):
            if not line.startswith("SPL\t"):
                continue
            parts = line.split("\t")
            if len(parts) < 8:
                continue
            acc_name = parts[4]
            if acc_name in h_accounts:
                h_spl_indices.append(i)
            elif acc_name == GST_ACCOUNT_NAME:
                gst_spl_indices.append(i)

        # If there are no H-account splits, leave this group unchanged
        if not h_spl_indices:
            adjusted_groups.append(grp)
            continue

        # Build new group:
        #  - For any H-account SPL: use gross/1.13 (net), keeping the SPL's sign
        #  - Drop any GST/HST Payable SPL lines
        new_grp: list[str] = []
        for i, line in enumerate(grp):
            if i in h_spl_indices:
                parts = line.split("\t")
                orig_amt = parse_amount(parts[7])
                sign = 1.0 if orig_amt >= 0 else -1.0
                net_amt = round(gross / H_RATE, 2) * sign
                parts[7] = f"{net_amt:.2f}"
                new_grp.append("\t".join(parts))
            elif i in gst_spl_indices:
                # Drop GST/HST Payable split
                continue
            else:
                new_grp.append(line)

        adjusted_groups.append(new_grp)
        adjusted_count += 1

    out_lines = header
    for grp in adjusted_groups:
        out_lines.extend(grp)

    dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(
        f"Wrote adjusted IIF to {dst} "
        f"(adjusted {adjusted_count} transaction group(s) with H-accounts)"
    )


def main(argv=None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Adjust H-coded IIF splits to avoid duplicate GST/HST."
    )
    parser.add_argument("input_iif", help="Input IIF file")
    parser.add_argument("output_iif", help="Output IIF file")
    parser.add_argument(
        "--h-accounts",
        default=None,
        help="Optional path to h_accounts.txt (default: config/h_accounts.txt)",
    )
    args = parser.parse_args(argv or sys.argv[1:])

    h_accounts = load_h_accounts(args.h_accounts)
    adjust_file(args.input_iif, args.output_iif, h_accounts)
    return

def _legacy_main(argv=None) -> None:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(
            "Usage: python tools/adjust_h_accounts_iif.py "
            "<input.iif> <output.iif>"
        )
        sys.exit(1)
    adjust_file(argv[0], argv[1], load_h_accounts(None))


if __name__ == "__main__":
    main()

