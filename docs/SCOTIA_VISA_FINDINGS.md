# Scotia Visa Credit Card Statement Analysis

## Structure Discovered

### Transaction Tables
- **Table 2** (Camelot index 1): First page transactions (13 transactions)
- **Table 6** (Camelot index 5): Second page transactions (6 transactions)
- **Total**: ~19 transactions per statement

### Header Structure
```
Row 0: [empty] | "TRANS." | "POST" | [empty] | [empty]
Row 1: "REF.#" | "DATE" | "DATE" | "DETAILS" | "AMOUNT($)"
Row 2: Account holder name (skip this row)
Row 3+: Transactions
```

### Column Mapping
- **Column 0**: REF.# (3-digit transaction reference number)
- **Column 1**: TRANS. DATE (transaction date, e.g., "Dec 1")
- **Column 2**: POST DATE (posting date, e.g., "Dec 3")
- **Column 3**: DETAILS (merchant name and location)
- **Column 4**: AMOUNT($) (amount with sign)

### Date Format
- Format: "Dec 1", "Dec 3", "Jan 2" (Month DD, no year)
- Need to extract year from statement period: "Dec 3, 2024 - Jan 2, 2025"
- Use POST DATE for transaction date (more accurate)

### Amount Format
- **Charges**: "11.28", "35.00" (positive, no sign)
- **Payments**: "300.00-" (trailing minus = negative)
- Need to parse trailing minus correctly

### Example Transactions
```
Row 3: REF=001, Date=Dec 1/Dec 3, Merchant="THE HOME DEPOT #7241 MILTON ON", Amount=11.28 (CHARGE)
Row 7: REF=005, Date=Dec 12/Dec 12, Merchant="PAYMENT FROM - *****01*8616", Amount=300.00- (PAYMENT)
```

### Subtotals
- Row with "SUB-TOTAL CREDITS" = Total payments (negative amounts)
- Row with "SUB-TOTAL DEBITS" = Total charges (positive amounts)
- These should be skipped (not transactions)

## What Needs to Be Fixed in extract_bank_statements.py

### 1. Credit Card Detection
- Currently: Only detects bank accounts
- Needed: Detect credit card statements (look for "VISA", "AMOUNT($)" header, etc.)

### 2. Transaction Table Detection
- Currently: Looks for "Withdrawals" and "Deposits" columns
- Needed: Look for "REF.#" and "AMOUNT($)" columns

### 3. Date Parsing
- Currently: Assumes full date format
- Needed: Parse "Dec 1" format and add year from statement period

### 4. Amount Parsing
- Currently: Expects separate Withdrawals/Deposits columns
- Needed: Parse single Amount column, handle trailing minus for payments

### 5. Output Format
- Currently: Returns DataFrame with "Withdrawals" and "Deposits" columns
- Needed: Return DataFrame with single "Amount" column where:
  - Positive = Charges (purchases)
  - Negative = Payments (you paid the card)

### 6. Multiline Descriptions
- Some merchant names may span multiple lines
- Need to handle continuation rows

## Expected Output Format

For credit cards, `extract_bank_statements.py` should return:
```python
DataFrame with columns:
- Date: "2024-12-03" (full date with year)
- Description: "THE HOME DEPOT #7241 MILTON ON"
- Amount: 11.28 (positive for charges)
- Amount: -300.00 (negative for payments)
```

Then `pdf_to_quickbooks.py` will:
1. Detect it's a credit card
2. Invert signs: Amount = -Amount (for AI model)
3. Process with AI
4. Revert signs back for Excel output





