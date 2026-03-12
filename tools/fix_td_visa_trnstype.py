#!/usr/bin/env python3
"""
Normalize TRNSTYPE values for TD Visa 6157 IIF:
- Change CHEQUE  -> CREDIT CARD
- Change DEPOSIT -> CCARD REFUND

This keeps all amounts and accounts identical; it only updates the
TRNSTYPE column for both TRNS and SPL rows so the file matches the
standard credit-card pattern used elsewhere (e.g. BMO_Credit_Card_2589).

Usage (from repo root):

  .venv\\Scripts\\python.exe tools\\fix_td_visa_trnstype.py \\
      "data\\iif\\114 - lovely\\TD Visa - 6157_raw.iif" \\
      "data\\iif\\114 - lovely\\TD Visa - 6157_ccard_raw.iif"
"""

from pathlib import Path
import sys


def fix_trnstype(input_path: str, output_path: str) -> None:
    src = Path(input_path)
    dst = Path(output_path)

    if not src.exists():
        print(f"❌ Input IIF not found: {src}")
        return

    lines = src.read_text(encoding="utf-8").splitlines()
    out_lines = []
    changed = 0

    for line in lines:
        if not line or line.startswith("!"):
            out_lines.append(line)
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            out_lines.append(line)
            continue

        tag = parts[0]
        trnstype = parts[2]

        if tag in {"TRNS", "SPL"}:
            if trnstype == "CHEQUE":
                parts[2] = "CREDIT CARD"
                changed += 1
            elif trnstype == "DEPOSIT":
                parts[2] = "CCARD REFUND"
                changed += 1

        out_lines.append("\t".join(parts))

    dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(
        f"Wrote fixed IIF to {dst} "
        f"(updated TRNSTYPE on {changed} TRNS/SPL line(s))"
    )


def main(argv=None) -> None:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(
            "Usage: python tools/fix_td_visa_trnstype.py "
            "<input.iif> <output.iif>"
        )
        sys.exit(1)
    fix_trnstype(argv[0], argv[1])


if __name__ == "__main__":
    main()

