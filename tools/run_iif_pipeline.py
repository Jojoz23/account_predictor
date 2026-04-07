#!/usr/bin/env python3
"""
Run the standard Excel -> IIF pipeline in one command:
1) excel_to_iif.py
2) update_iif_account_names.py
3) optional transfer cleanup (bank <-> card)
4) optional H-account net adjustment
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(cmd)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end IIF pipeline.")
    parser.add_argument("--excel", required=True, help="Input Excel file path")
    parser.add_argument("--raw-iif", default=None, help="Path for raw IIF output")
    parser.add_argument("--mapped-iif", default=None, help="Path for mapped IIF output")
    parser.add_argument("--final-iif", default=None, help="Path for final IIF output")
    parser.add_argument("--qb-account", default=None, help="QuickBooks bank/card account name for excel_to_iif -a")

    parser.add_argument("--map-file", default=None, help="Account mapping CSV for update_iif_account_names.py")
    parser.add_argument("--accounts-txt", default=None, help="QuickBooks Accounts.TXT for type preservation")

    parser.add_argument("--skip-transfer-cleanup", action="store_true", help="Skip transfer cleanup step")
    parser.add_argument("--bank-iif", default=None, help="Bank IIF used to remove duplicate transfers from card IIF")
    parser.add_argument("--card-account", default=None, help="Card account name (for transfer cleanup)")
    parser.add_argument("--bank-account", default=None, help="Bank account name (for transfer cleanup)")
    parser.add_argument(
        "--transfer-mode",
        choices=["generic", "visa_td5931"],
        default="generic",
        help="Transfer cleanup mode",
    )
    parser.add_argument("--visa-account", default=None, help="Visa account name for visa_td5931 mode")
    parser.add_argument("--td5931-account", default=None, help="TD bank account name for visa_td5931 mode")

    parser.add_argument("--skip-h-net", action="store_true", help="Skip H-account net adjustment")
    parser.add_argument("--h-accounts", default=None, help="Path to h_accounts.txt")
    args = parser.parse_args(argv or sys.argv[1:])

    root = Path(__file__).resolve().parent.parent
    py = sys.executable

    excel_path = Path(args.excel)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel not found: {excel_path}")

    raw_iif = Path(args.raw_iif) if args.raw_iif else excel_path.with_name(f"{excel_path.stem}_raw.iif")
    mapped_iif = Path(args.mapped_iif) if args.mapped_iif else excel_path.with_name(f"{excel_path.stem}_mapped.iif")
    final_iif = Path(args.final_iif) if args.final_iif else excel_path.with_name(f"{excel_path.stem}_final.iif")

    # Step 1: Excel -> raw IIF
    cmd_1 = [py, str(root / "excel_to_iif.py"), str(excel_path), "-o", str(raw_iif)]
    if args.qb_account:
        cmd_1.extend(["-a", args.qb_account])
    run_cmd(cmd_1)

    # Step 2: Map names/types -> mapped IIF
    cmd_2 = [py, str(root / "update_iif_account_names.py"), str(raw_iif), "-o", str(mapped_iif)]
    if args.map_file:
        cmd_2.extend(["-m", args.map_file])
    if args.accounts_txt:
        cmd_2.extend(["-a", args.accounts_txt])
    run_cmd(cmd_2)

    current_iif = mapped_iif

    # Step 3: Optional transfer cleanup
    if not args.skip_transfer_cleanup:
        cleaned_iif = mapped_iif.with_name(f"{mapped_iif.stem}_no_transfers.iif")
        if args.transfer_mode == "generic":
            if args.bank_iif and args.card_account and args.bank_account:
                run_cmd(
                    [
                        py,
                        str(root / "scripts" / "remove_duplicate_transfers.py"),
                        args.bank_iif,
                        str(mapped_iif),
                        "-c",
                        args.card_account,
                        "-b",
                        args.bank_account,
                        "-o",
                        str(cleaned_iif),
                    ]
                )
                current_iif = cleaned_iif
            else:
                print("Skipping transfer cleanup (provide --bank-iif --card-account --bank-account).")
        else:
            if args.visa_account and args.td5931_account:
                run_cmd(
                    [
                        py,
                        str(root / "tools" / "remove_visa_td5931_transfers.py"),
                        str(mapped_iif),
                        str(cleaned_iif),
                        args.visa_account,
                        args.td5931_account,
                    ]
                )
                current_iif = cleaned_iif
            else:
                print("Skipping visa_td5931 cleanup (provide --visa-account --td5931-account).")

    # Step 4: Optional H-net
    if args.skip_h_net:
        if current_iif != final_iif:
            final_iif.write_text(current_iif.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        cmd_4 = [py, str(root / "tools" / "adjust_h_accounts_iif.py"), str(current_iif), str(final_iif)]
        if args.h_accounts:
            cmd_4.extend(["--h-accounts", args.h_accounts])
        run_cmd(cmd_4)

    print(f"\nPipeline complete. Final IIF: {final_iif}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

