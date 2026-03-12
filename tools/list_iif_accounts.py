#!/usr/bin/env python3
"""
List unique ACCNT names used in TRNS/SPL lines of an IIF file.

Usage:
  .venv\\Scripts\\python.exe tools\\list_iif_accounts.py "path\\to\\file.iif"
"""

from pathlib import Path
import sys


def list_accounts(iif_path: str) -> None:
    path = Path(iif_path)
    if not path.exists():
        print(f"❌ IIF not found: {path}")
        return

    accounts = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("!"):
            continue
        parts = line.split("\t")
        if len(parts) >= 5 and parts[0] in {"TRNS", "SPL"}:
            accounts.add(parts[4])

    for name in sorted(accounts):
        print(name)


def main(argv=None) -> None:
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print("Usage: list_iif_accounts.py <file.iif>")
        sys.exit(1)
    list_accounts(argv[0])


if __name__ == "__main__":
    main()

