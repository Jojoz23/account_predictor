#!/usr/bin/env python3
"""
Remove TD Visa payment transactions that hit TD 5931 from a Visa IIF.

Intended usage after normalising TRNSTYPE to CREDIT CARD / CCARD REFUND:
  - Drop any TRNS/SPL/ENDTRNS group where:
      * TRNS ACCNT is the Visa account (e.g. "TD Visa - 6157"), AND
      * TRNS TRNSTYPE is "CCARD REFUND" (card payment/refund), AND
      * At least one SPL line uses the TD 5931 bank account.

Amounts and other transactions are left unchanged.

Usage (from repo root):

  .venv\\Scripts\\python.exe tools\\remove_td_visa_td5931_payments.py \\
      "data\\iif\\114 - lovely\\TD Visa - 6157_ccard_raw.iif" \\
      "data\\iif\\114 - lovely\\TD Visa - 6157_ccard_no_td5931_payments.iif" \\
      "TD Visa - 6157" \\
      "TD 5931"
"""

from pathlib import Path
import sys
from typing import List


def remove_payments(
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

    # Copy header (up to !ENDTRNS)
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

    kept_groups: List[List[str]] = []
    removed = 0

    for grp in groups:
        if not grp:
            continue

        trns = grp[0].split("\t")
        if len(trns) < 5:
            kept_groups.append(grp)
            continue

        trnstype = trns[2]
        trns_accnt = trns[4]

        is_ccard_payment = (
            trnstype == "CCARD REFUND"
            and trns_accnt == visa_account_name
        )

        touches_td5931 = False
        if is_ccard_payment:
            for line in grp:
                if not line.startswith("SPL\t"):
                    continue
                parts = line.split("\t")
                if len(parts) < 5:
                    continue
                if parts[4] == td5931_account_name:
                    touches_td5931 = True
                    break

        if is_ccard_payment and touches_td5931:
            removed += 1
            continue

        kept_groups.append(grp)

    out_lines: List[str] = header
    for grp in kept_groups:
        out_lines.extend(grp)

    dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(
        f"Wrote Visa IIF without TD 5931 payments to {dst} "
        f"(removed {removed} payment transaction(s))"
    )


def main(argv=None) -> None:
    argv = argv or sys.argv[1:]
    if len(argv) != 4:
        print(
            "Usage: python tools/remove_td_visa_td5931_payments.py "
            "<input.iif> <output.iif> <visa_account_name> <td5931_account_name>"
        )
        sys.exit(1)

    remove_payments(argv[0], argv[1], argv[2], argv[3])


if __name__ == "__main__":
    main()

