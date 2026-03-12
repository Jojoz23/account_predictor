#!/usr/bin/env python3
"""
Build a subset IIF containing:

  1) All transactions that hit one of the H_ACCOUNTS
     (Office Supplies, Repairs and Maintenance, Telephone Expense, Utilities)
  2) All transactions that have a GST/HST Payable split,
     where the non-GST side is NOT one of the H_ACCOUNTS.

This is intended for importing into a QuickBooks dummy file so you can
verify H-tax behaviour and GST/HST Payable behaviour without importing
the client's entire bank history.

Usage (from repo root):

  .venv\\Scripts\\python.exe tools\\build_gst_h_subset_iif.py ^
      "data\\iif\\114 - lovely\\TD Bank - 5931_H_net_no_gst_splits.iif" ^
      "data\\iif\\114 - lovely\\TD Bank - 5931_dummy_H_and_GST_subset.iif"
"""

from pathlib import Path
import sys


H_ACCOUNTS = {
    "Office Supplies",
    "Repairs and Maintenance",
    "Telephone Expense",
    "Utilities",
}

GST_ACCOUNT_NAME = "GST/HST Payable"


def build_subset(input_path: str, output_path: str) -> None:
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

    subset_groups = []
    kept_count = 0

    for grp in groups:
        has_h_account = False
        has_gst_split = False

        for line in grp:
            if not line.startswith("SPL\t"):
                continue
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            acc_name = parts[4]
            if acc_name in H_ACCOUNTS:
                has_h_account = True
            if acc_name == GST_ACCOUNT_NAME:
                has_gst_split = True

        keep = False
        if has_h_account:
            # Any transaction touching an H-account
            keep = True
        elif has_gst_split:
            # GST/HST Payable present, and no H-account in this group
            keep = True

        if keep:
            subset_groups.append(grp)
            kept_count += 1

    out_lines = header
    for grp in subset_groups:
        out_lines.extend(grp)

    dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(
        f"Wrote subset IIF to {dst} "
        f"(kept {kept_count} transaction(s) out of {len(groups)})"
    )


def main(argv=None) -> None:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(
            "Usage: python tools/build_gst_h_subset_iif.py "
            "<input.iif> <output.iif>"
        )
        sys.exit(1)
    build_subset(argv[0], argv[1])


if __name__ == "__main__":
    main()

