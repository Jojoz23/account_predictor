#!/usr/bin/env python3
from pathlib import Path


def main() -> None:
    path = Path(r"data/iif/114 - lovely/TD Bank - 5931_dummy_H_and_GST_subset.iif")
    lines = path.read_text(encoding="utf-8").splitlines()

    total = 0.0
    count = 0

    for line in lines:
        if not line.startswith("TRNS\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        try:
            amt = float(parts[7])
        except Exception:
            continue
        total += amt
        count += 1

    print(f"Transactions counted: {count}")
    print(f"Net change TD BANK - 5931 (subset): {total:.2f}")


if __name__ == "__main__":
    main()

