#!/usr/bin/env python3
"""
Remove all TD Visa ↔ TD 5931 transfer transactions from a Visa IIF.

We drop any TRNS/SPL/ENDTRNS group where:
  - TRNS ACCNT == <visa_account_name>  (e.g. "TD Visa - 6157")
  - and at least one SPL ACCNT == <td5931_account_name> (e.g. "TD BANK - 5931")

This removes:
  - CCARD REFUND payments from TD 5931 to the Visa, and
  - CREDIT CARD cash advances from the Visa into TD 5931,
so that all those transfers live only in the TD 5931 bank IIF.

Usage (from repo root):

  .venv\\Scripts\\python.exe tools\\remove_visa_td5931_transfers.py \\
      "data\\iif\\114 - lovely\\TD Visa - 6157_final.iif" \\
      "data\\iif\\114 - lovely\\TD Visa - 6157_final_no_td5931_transfers.iif" \\
      "TD Visa - 6157" \\
      "TD BANK - 5931"
"""

from pathlib import Path
import sys
from typing import List


def remove_transfers(
    input_path: str,
    output_path: str,
    visa_account_name: str,
    td5931_account_name: str,
) -> None:
    src = Path(input_path)
    dst = Path(output_path)

    if not src.exists():
        print(f"❌ Input IIF not found: {src}")
        return

    lines = src.read_text(encoding="utf-8").splitlines()

    # Copy header (up to !ENDTRNS if present)
    header: List[str] = []
    idx = 0
    while idx < len(lines):
        header.append(lines[idx])
        if lines[idx].startswith("!ENDTRNS"):
            idx += 1
            break
        idx += 1

    # Group TRNS/SPL/ENDTRNS blocks
    groups: List[List[str]] = []
    cur: List[str] = []
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

    kept: List[List[str]] = []
    removed = 0

    for grp in groups:
        if not grp:
            continue
        trns_parts = grp[0].split("\t")
        if len(trns_parts) < 5:
            kept.append(grp)
            continue

        trns_accnt = trns_parts[4]

        is_visa_trns = trns_accnt == visa_account_name
        touches_td5931 = False
        if is_visa_trns:
            for line in grp:
                if not line.startswith("SPL\t"):
                    continue
                parts = line.split("\t")
                if len(parts) < 5:
                    continue
                if parts[4] == td5931_account_name:
                    touches_td5931 = True
                    break

        if is_visa_trns and touches_td5931:
            removed += 1
            continue

        kept.append(grp)

    out_lines: List[str] = header
    for grp in kept:
        out_lines.extend(grp)

    dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(
        f"Wrote Visa IIF without TD BANK - 5931 transfers to {dst} "
        f"(removed {removed} transaction group(s))"
    )


def main(argv=None) -> None:
    argv = argv or sys.argv[1:]
    if len(argv) != 4:
        print(
            "Usage: python tools/remove_visa_td5931_transfers.py "
            "<input.iif> <output.iif> <visa_account_name> <td5931_account_name>"
        )
        sys.exit(1)

    remove_transfers(argv[0], argv[1], argv[2], argv[3])


if __name__ == "__main__":
    main()

