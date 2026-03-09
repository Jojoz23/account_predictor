#!/usr/bin/env python3
"""
Remove from the CREDIT CARD IIF the payment transactions that duplicate transfers
already in the CHEQUING IIF (bank). So you keep the transfer in the chequing file
and remove it from the card file — one transfer, one place.

We read the bank IIF to find all transfers TO the card (date + amount), then remove
those same (date, amount) as CCARD REFUND / "TRSF FROM/DE ACCT/CPT" from the card IIF.

Usage:
  python remove_duplicate_transfers.py "BMO_Business_Che_7779_mapped.iif" "BMO_Credit_Card_2589_mapped.iif" -o "BMO_Credit_Card_2589_mapped_no_xfer.iif"
"""

from pathlib import Path


def get_transfers_from_bank_iif(bank_iif_path, card_account_name):
    """
    Return (transfers_to_card, deposits_from_card).
    - transfers_to_card: set of (date, amount) for CHEQUE/TRANSFER from bank TO card.
    - deposits_from_card: set of (date, amount) for DEPOSIT in bank FROM card (so we can remove the card-side "TRSF TO" entry).
    """
    path = Path(bank_iif_path)
    if not path.exists():
        print(f"ERROR: Bank file not found: {path}")
        return set(), set()
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    transfers_to_card = set()
    deposits_from_card = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('TRNS\t') and not line.startswith('!'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 8:
                trns_type = parts[2]
                date_str = parts[3].strip()
                amount_str = parts[7].strip()
                try:
                    amount = float(amount_str)
                except ValueError:
                    amount = 0
                if i + 1 < len(lines) and lines[i + 1].startswith('SPL\t'):
                    spl_parts = lines[i + 1].rstrip('\n').split('\t')
                    if len(spl_parts) >= 5:
                        spl_account = spl_parts[4].strip()
                        if spl_account == card_account_name and amount < 0 and trns_type in ('CHEQUE', 'CHECK', 'TRANSFER'):
                            transfers_to_card.add((date_str, round(abs(amount), 2)))
                        # Bank DEPOSIT with SPL to card account = money received from card (duplicate of card's "TRSF TO" bank)
                        if spl_account == card_account_name and trns_type == 'DEPOSIT' and amount > 0:
                            deposits_from_card.add((date_str, round(amount, 2)))
        i += 1
    return transfers_to_card, deposits_from_card


def remove_transfers_from_card_iif(card_iif_path, bank_transfers_to_card, bank_deposits_from_card, bank_account_name, output_path=None):
    """Remove from card IIF: (1) CCARD REFUND TRSF FROM matching bank_transfers_to_card, (2) TRSF TO bank matching bank_deposits_from_card."""
    path = Path(card_iif_path)
    if not path.exists():
        print(f"ERROR: Card file not found: {path}")
        return None
    if output_path is None:
        output_path = path.parent / (path.stem + "_no_xfer.iif")
    else:
        output_path = Path(output_path)

    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    out = []
    i = 0
    removed = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.startswith('TRNS\t') and not line.startswith('!'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 9:
                trns_type = parts[2]
                date_str = parts[3].strip()
                amount_str = parts[7].strip()
                memo = (parts[9] if len(parts) > 9 else '').strip()
                try:
                    amount = float(amount_str)
                except ValueError:
                    amount = 0
                key = (date_str, round(abs(amount), 2))
                # (1) CCARD REFUND = payment to card from bank; same as bank's transfer to card
                is_transfer_from_bank = (
                    trns_type == 'CCARD REFUND'
                    and 'TRSF FROM' in memo.upper()
                    and key in bank_transfers_to_card
                )
                # (2) Card sending to bank (TRSF TO) — need to check SPL account is bank
                is_transfer_to_bank = (
                    'TRSF TO' in memo.upper()
                    and key in bank_deposits_from_card
                )
                if is_transfer_to_bank and i + 1 < len(lines) and lines[i + 1].startswith('SPL\t'):
                    spl_parts = lines[i + 1].rstrip('\n').split('\t')
                    if len(spl_parts) >= 5 and spl_parts[4].strip() == bank_account_name:
                        pass  # keep is_transfer_to_bank True
                    else:
                        is_transfer_to_bank = False
                if is_transfer_from_bank:
                    out.pop()
                    i += 1
                    if i < len(lines) and lines[i].startswith('SPL\t'):
                        i += 1
                    if i < len(lines) and lines[i].strip() == 'ENDTRNS':
                        i += 1
                    removed += 1
                    print(f"  Removed payment: {date_str} {amount:.2f} (duplicate of bank->card transfer)")
                    continue
                if is_transfer_to_bank:
                    out.pop()
                    i += 1
                    if i < len(lines) and lines[i].startswith('SPL\t'):
                        i += 1
                    if i < len(lines) and lines[i].strip() == 'ENDTRNS':
                        i += 1
                    removed += 1
                    print(f"  Removed payment: {date_str} {abs(amount):.2f} (duplicate of card->bank transfer)")
                    continue
        i += 1

    # Renumber TRNS/SPL ids
    trns_id = 0
    new_lines = []
    for line in out:
        if line.startswith('TRNS\t') and not line.startswith('!'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2:
                parts[1] = str(trns_id)
                new_lines.append('\t'.join(parts) + '\n')
                trns_id += 1
        elif line.startswith('SPL\t') and not line.startswith('!'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2 and trns_id > 0:
                parts[1] = str(trns_id - 1)
            new_lines.append('\t'.join(parts) + '\n')
        else:
            new_lines.append(line)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"Removed {removed} duplicate transfer(s) from card IIF. Wrote {output_path}")
    return output_path


def main():
    import argparse
    p = argparse.ArgumentParser(
        description='Remove duplicate transfers from credit card IIF (keep them in chequing IIF)'
    )
    p.add_argument('bank_iif', help='Path to bank/chequing IIF (mapped)')
    p.add_argument('card_iif', help='Path to credit card IIF (mapped)')
    p.add_argument('-c', '--card-account', default='BMO World Elite Mastercard 2589',
                   help='QuickBooks name of the credit card account (used to find transfers in bank IIF)')
    p.add_argument('-b', '--bank-account', default='BMO-7779',
                   help='QuickBooks name of the bank account (used to match card→bank transfers)')
    p.add_argument('-o', '--output', default=None, help='Output path for card IIF (default: card stem + _no_xfer.iif)')
    args = p.parse_args()

    transfers_to_card, deposits_from_card = get_transfers_from_bank_iif(args.bank_iif, args.card_account)
    print(f"Bank->card transfers in bank IIF: {len(transfers_to_card)} {transfers_to_card}")
    print(f"Card->bank deposits in bank IIF:  {len(deposits_from_card)} {deposits_from_card}")
    remove_transfers_from_card_iif(
        args.card_iif, transfers_to_card, deposits_from_card, args.bank_account, args.output
    )


if __name__ == '__main__':
    main()
