### Excel → IIF workflow for QuickBooks Desktop

This document summarizes the end‑to‑end process we’re using to go from **processed Excel statements** to **final IIF files** that:

- Use **canonical QuickBooks account names** (from `Account_final.txt` + `Accounts.TXT`)
- Include **GST/HST splits** from the Excel `GST`/`HST` column
- Avoid **double‑counting bank ↔ card transfers**
- Prevent **double taxation** on H‑coded expense accounts by converting them to **net** and removing explicit GST splits

This applies to:

- Bank accounts (e.g. `TD BANK - 5931`)
- Credit cards (e.g. `TD VISA - 6157`, `TD VISA - 7744`, `AMEX - 6002`)

---

### 1. Prerequisites and conventions

- **Excel inputs** live under:  
  `data/iif/114 - lovely/*.xlsx`
- **Canonical QB accounts**:  
  `data/iif/114 - lovely/Account_final.txt`
- **Account name mapping CSV**:  
  `data/iif/114 - lovely/account_names_map_114.csv`
- **QuickBooks Chart of Accounts export** (ASCII):  
  `data/iif/114 - lovely/Accounts.TXT`
- All commands are run from the project root using the venv Python:

```bash
.venv\Scripts\python.exe ...
```

---

### 2. Step 1 – Excel → base IIF with GST splits

Use `excel_to_iif.py` to convert a **single** Excel file into an IIF that:

- Derives `TRNS`/`SPL` rows from the bank/credit card data
- Reads `GST` / `HST` / `GST/HST` column when present
- Splits each **gross** amount with GST into:
  - **Net** to the expense/income account
  - **GST** to `GST/HST Payable`

#### 2.1 Bank accounts (TD 5931 example)

```bash
.venv\Scripts\python.exe excel_to_iif.py ^
  "data\iif\114 - lovely\TD Bank - 5931.xlsx" ^
  -o "data\iif\114 - lovely\TD Bank - 5931_with_gst_raw.iif"
```

Key behaviour:

- If Excel has **`Withdrawals` / `Deposits`** and a **`GST`/`HST`** column:
  - `withdrawal > 0` → `TRNSTYPE = CHEQUE`, **negative** bank `Amount`
  - `deposit > 0` → `TRNSTYPE = DEPOSIT`, **positive** bank `Amount`
  - When `GST > 0` for a row with gross `G`:
    - **Net** = `G - GST` → SPL to the main expense/income account
    - **GST** → SPL to `GST/HST Payable`
- Blank or missing `Account` cells are defaulted to **`Ask My Accountant`**.

#### 2.2 Credit cards (Visa / Amex example)

```bash
.venv\Scripts\python.exe excel_to_iif.py ^
  "data\iif\114 - lovely\TD Visa - 6157.xlsx" ^
  -o "data\iif\114 - lovely\TD Visa - 6157_with_gst_raw.iif" ^
  --skip-accounts
```

Key behaviour:

- For credit cards, Excel has a single **`Amount`** column:
  - `Amount > 0`  → purchase/charge → `TRNSTYPE = CREDIT CARD`
  - `Amount < 0`  → payment/refund → `TRNSTYPE = CCARD REFUND`
- If there is a **`GST`/`HST`** column and `Amount > 0`:
  - Gross `G` (positive) is split into:
    - **Net** = `G - GST` → SPL to expense account
    - **GST** → SPL to `GST/HST Payable`

At this stage the IIF has:

- Correct **GST splits**
- Raw **statement account names** (e.g. `Office Expense`, `Vehicle Expense`, `Dues and Subscription`), not yet normalized

---

### 3. Step 2 – Normalize TRNSTYPE for credit cards

Because some card exports may initially be tagged as `CHEQUE`/`DEPOSIT`, we normalize them to the standard credit‑card types using:

`tools/fix_td_visa_trnstype.py`

```bash
.venv\Scripts\python.exe tools\fix_td_visa_trnstype.py ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_raw.iif" ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_ccard_raw.iif"
```

This keeps all amounts the same but rewrites:

- `CHEQUE`   → `CREDIT CARD`
- `DEPOSIT`  → `CCARD REFUND`

for both `TRNS` and `SPL` lines.

---

### 4. Step 3 – Remove Visa/Amex payments sourced from TD 5931

To avoid **double‑counting payments**, we remove card transactions whose payment side is already present in the TD 5931 bank IIF.

#### 4.1 Remove CCARD REFUND payments from the card file

Use `tools/remove_td_visa_td5931_payments.py`:

```bash
.venv\Scripts\python.exe tools\remove_td_visa_td5931_payments.py ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_ccard_raw.iif" ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_ccard_no_td5931_payments.iif" ^
  "TD Visa - 6157" ^
  "TD 5931"
```

This drops any transaction group where:

- `TRNS ACCNT` is the Visa/Amex account, **and**
- `TRNSTYPE = CCARD REFUND` (refund/payment), **and**
- One of the `SPL` lines uses `TD 5931` as the account.

#### 4.2 Optionally also drop cash‑advance style transfers

To also remove **cash advances** (card → TD BANK ‑ 5931) so that *all* bank‑side flows live only in the TD 5931 file, use:

`tools/remove_visa_td5931_transfers.py`

```bash
.venv\Scripts\python.exe tools\remove_visa_td5931_transfers.py ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_mapped.iif" ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_final_no_td5931_transfers.iif" ^
  "TD Visa - 6157" ^
  "TD BANK - 5931"
```

This removes any transaction group where:

- `TRNS ACCNT` = Visa/Amex account, and
- At least one `SPL` line uses `TD BANK - 5931`.

---

### 5. Step 4 – Map accounts to canonical QB names and set ACCNTTYPE

To ensure IIF account names/types exactly match QuickBooks, we use:

`update_iif_account_names.py`

```bash
.venv\Scripts\python.exe update_iif_account_names.py ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_ccard_no_td5931_payments.iif" ^
  -m "data\iif\114 - lovely\account_names_map_114.csv" ^
  -a "data\iif\114 - lovely\Accounts.TXT" ^
  -o "data\iif\114 - lovely\TD Visa - 6157_with_gst_mapped.iif"
```

Behaviour:

- **Name mapping** via `account_names_map_114.csv`:
  - e.g.  
    `Office Expense` → `Office Supplies`  
    `Vehicle Expense` → `Automobile Expense`  
    `Dues and Subscription` → `Membership & Subscriptions`  
    `Computer and Internet Expense` → `Computer and Internet Expenses`
- **Account types** via `Accounts.TXT`:
  - ACCNT rows get their `ACCNTTYPE` (e.g. `BANK`, `CCARD`, `EXP`, `EXEXP`, etc.) from QuickBooks’ export, so we **don’t** try to change types on import (avoids error 3210).

After this step, all account names in the IIF should be present in `Account_final.txt` and exactly match the QuickBooks chart.

---

### 6. Step 5 – Net H‑coded accounts and remove explicit GST for them

QuickBooks H‑coded expense accounts automatically calculate GST/HST.  
If we also import explicit `GST/HST Payable` splits for them, QB **double‑taxes**.

We fix this by:

- Converting H‑account SPL amounts from **gross** to **net** (divide by 1.13)
- Dropping the `GST/HST Payable` SPL

This is done for both bank (chequing) and card IIFs using:

`tools/adjust_h_accounts_iif.py`

#### 6.1 H‑account list

In `adjust_h_accounts_iif.py`:

```python
H_ACCOUNTS = {
    "Office Supplies",
    "Repairs and Maintenance",
    "Telephone Expense",
    "Utilities",
    "Automobile Expense",
    "Computer and Internet Expenses",
    "Meals and Entertainment",
}
```

These are the accounts in QuickBooks that carry **Sales Tax Code H**.

#### 6.2 Running the netting script

Bank example (TD 5931):

```bash
.venv\Scripts\python.exe tools\adjust_h_accounts_iif.py ^
  "data\iif\114 - lovely\TD Bank - 5931_with_gst_final.iif" ^
  "data\iif\114 - lovely\TD Bank - 5931_H_net_no_gst_splits.iif"
```

Visa example:

```bash
.venv\Scripts\python.exe tools\adjust_h_accounts_iif.py ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_final_no_td5931_transfers.iif" ^
  "data\iif\114 - lovely\TD Visa - 6157_with_gst_H_net_no_gst_splits.iif"
```

What it does per transaction group:

- Compute `gross = abs(TRNS AMOUNT)`
- For every `SPL` to an H account:
  - Replace `SPL amount` with `sign * round(gross / 1.13, 2)`
- Remove any `SPL` to `GST/HST Payable` in that group

Result:

- **Bank/TRNS amount** remains the original **gross** (matches statement/Excel)
- H expense account carries the **net** base; QB’s H tax code recalculates 13% on top
- No double taxation, and cheque/charge totals still match the source data.

---

### 7. Final import files per account

For the 114 company we ended up with (examples):

- **TD BANK - 5931**:  
  `TD Bank - 5931_H_net_no_gst_splits.iif`
- **TD VISA - 6157**:  
  `TD Visa - 6157_with_gst_H_net_no_gst_splits.iif`
- **TD VISA - 7744**:  
  `TD Visa - 7744_with_gst_H_net_no_gst_splits.iif`
- **AMEX - 6002** (after running the same pipeline):  
  `Working Amex - 6002_..._with_gst_H_net_no_gst_splits.iif` (name will follow the same pattern)

These are the files to import into the **real QuickBooks file** after:

- Taking a backup of the QB company
- Verifying that the H tax code is correctly applied to the same accounts listed in `H_ACCOUNTS`
- Spot‑checking a few transactions for:
  - Bank/CC balance changes
  - Net vs tax for H‑coded expenses
  - Explicit `GST/HST Payable` on non‑H accounts only

