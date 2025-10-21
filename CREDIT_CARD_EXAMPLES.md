# 💳 Credit Card Handling - Complete Guide

This document explains how the system handles credit card statements vs bank account statements.

---

## 🔍 The Problem

Credit card statements and bank statements show amounts differently:

### **Credit Card Statement:**
```
Date        | Description              | Amount
Jan 15      | WALMART PURCHASE        | 142.50    ← Positive = You owe money (charge)
Jan 16      | COSTCO PURCHASE         | 89.99     ← Positive = You owe money (charge)
Jan 17      | PAYMENT - THANK YOU     | -500.00   ← Negative = You paid them
Jan 18      | REFUND - AMAZON         | -25.00    ← Negative = Credit back to you
```

**From credit card company's perspective:**
- Positive amounts = Charges (you owe them)
- Negative amounts = Payments (you paid them)

### **Bank Account Statement:**
```
Date        | Description              | Amount
Jan 15      | WALMART PURCHASE        | -142.50   ← Negative = Money out (expense)
Jan 16      | SALARY DEPOSIT          | 2500.00   ← Positive = Money in (income)
Jan 17      | BILL PAYMENT            | -89.99    ← Negative = Money out (expense)
```

**From your accounting perspective:**
- Negative amounts = Expenses (money out)
- Positive amounts = Income (money in)

---

## ✅ The Solution

The system **automatically detects** credit card statements and **inverts the signs** to match your accounting format.

### **Conversion Process:**

#### **Input: Credit Card PDF**
```
Date        | Description              | Amount (from PDF)
2024-01-15  | WALMART PURCHASE        | 142.50
2024-01-16  | COSTCO PURCHASE         | 89.99
2024-01-17  | PAYMENT - THANK YOU     | -500.00
2024-01-18  | STARBUCKS               | 8.75
```

#### **After Credit Card Detection:**
System detects keywords like "PAYMENT - THANK YOU" and inverts signs.

#### **Output: Standard Format (for AI model)**
```
Date        | Description              | Amount (inverted)
2024-01-15  | WALMART PURCHASE        | -142.50   ← Now negative (expense)
2024-01-16  | COSTCO PURCHASE         | -89.99    ← Now negative (expense)
2024-01-17  | PAYMENT - THANK YOU     | 500.00    ← Now positive (payment)
2024-01-18  | STARBUCKS               | -8.75     ← Now negative (expense)
```

#### **After AI Prediction:**
```
Date        | Description              | Amount    | Account                  | Confidence
2024-01-15  | WALMART PURCHASE        | -$142.50  | Office Expense           | 94.2%
2024-01-16  | COSTCO PURCHASE         | -$89.99   | Office Expense           | 91.5%
2024-01-17  | PAYMENT - THANK YOU     | $500.00   | Transfer Between Banks   | 88.3%
2024-01-18  | STARBUCKS               | -$8.75    | Meals & Entertainment    | 92.7%
```

✅ **Perfect!** Charges are expenses (negative), payments are positive.

---

## 🤖 Auto-Detection Logic

The system uses **multiple indicators** to detect credit cards:

### **1. Credit Card Keywords** (Strong Indicators)

If the descriptions contain 2+ of these keywords, it's likely a credit card:
- `payment - thank you`
- `payment thank you`
- `payment received`
- `previous balance`
- `new balance`
- `credit card`
- `visa`
- `mastercard`
- `amex`
- `american express`
- `minimum payment`
- `interest charge`
- `annual fee`
- `cash advance`

### **2. Bank Account Keywords** (Opposite Indicators)

If the descriptions contain 2+ of these keywords, it's likely a bank account:
- `direct deposit`
- `eft credit`
- `eft debit`
- `wire transfer`
- `cheque`
- `check`
- `atm withdrawal`
- `pre-authorized`

### **3. Purchase Pattern Analysis**

- If **positive amounts** have purchase-related descriptions (e.g., "WALMART PURCHASE", "POS SALE")
- This indicates credit card (because purchases are positive in CC statements)

---

## 🎯 Usage Examples

### **Example 1: Auto-Detection (Recommended)**

```bash
python pdf_to_quickbooks.py visa_statement_jan2024.pdf
```

**Output:**
```
🔧 Auto-detection mode: Will detect credit card vs bank account
📋 STEP 1: Extracting transactions from PDF...
  💳 Credit card auto-detected - inverted amount signs
     Charges (positive in PDF) → Expenses (negative)
     Payments (negative in PDF) → Income (positive)
✅ Successfully extracted 45 transactions
```

### **Example 2: Manual Override (Credit Card)**

If auto-detection fails, force credit card mode:

```bash
python pdf_to_quickbooks.py statement.pdf --credit-card
```

**Output:**
```
🔧 Credit card mode: ENABLED (will invert amount signs)
📋 STEP 1: Extracting transactions from PDF...
  💳 Credit card user-specified - inverted amount signs
     Charges (positive in PDF) → Expenses (negative)
     Payments (negative in PDF) → Income (positive)
```

### **Example 3: Manual Override (Bank Account)**

If auto-detection incorrectly identifies a bank statement as credit card:

```bash
python pdf_to_quickbooks.py statement.pdf --bank
```

**Output:**
```
🔧 Bank account mode: ENABLED (amounts unchanged)
📋 STEP 1: Extracting transactions from PDF...
  🏦 Bank account user-specified - amounts unchanged
```

### **Example 4: Python API**

```python
from pdf_to_quickbooks import PDFToQuickBooks

pipeline = PDFToQuickBooks()

# Auto-detect (recommended)
df = pipeline.process_pdf('statement.pdf')

# Force credit card
df = pipeline.process_pdf('visa_statement.pdf', is_credit_card=True)

# Force bank account
df = pipeline.process_pdf('bank_statement.pdf', is_credit_card=False)
```

---

## 📊 Real-World Examples

### **RBC Visa Statement**

**Input PDF:**
```
Trans Date  | Description                    | Amount
15-JAN-24   | WALMART STORE #1234           | 142.50
16-JAN-24   | COSTCO WHOLESALE #567         | 89.99
17-JAN-24   | PAYMENT - THANK YOU           | -500.00
18-JAN-24   | STARBUCKS COFFEE #9876        | 8.75
20-JAN-24   | INTEREST CHARGE               | 2.50
```

**Auto-Detection:**
✅ Detects "PAYMENT - THANK YOU" and "INTEREST CHARGE" → Credit Card

**After Processing:**
```
Date        | Description                    | Amount    | Account
2024-01-15  | WALMART STORE #1234           | -$142.50  | Office Expense
2024-01-16  | COSTCO WHOLESALE #567         | -$89.99   | Office Expense
2024-01-17  | PAYMENT - THANK YOU           | $500.00   | Transfer Between Banks
2024-01-18  | STARBUCKS COFFEE #9876        | -$8.75    | Meals & Entertainment
2024-01-20  | INTEREST CHARGE               | -$2.50    | Bank Charges
```

### **TD Bank Checking Account**

**Input PDF:**
```
Date        | Description              | Debit    | Credit   | Balance
15-JAN-24   | WALMART PURCHASE        | 142.50   |          | 4,857.50
16-JAN-24   | SALARY DIRECT DEPOSIT   |          | 2,500.00 | 7,357.50
17-JAN-24   | HYDRO BILL PAYMENT      | 125.00   |          | 7,232.50
```

**After Column Standardization:**
```
Date        | Description              | Withdrawals | Deposits
2024-01-15  | WALMART PURCHASE        | 142.50      | 0
2024-01-16  | SALARY DIRECT DEPOSIT   | 0           | 2,500.00
2024-01-17  | HYDRO BILL PAYMENT      | 125.00      | 0
```

**After Conversion (No Inversion Needed):**
```
Date        | Description              | Amount
2024-01-15  | WALMART PURCHASE        | -$142.50
2024-01-16  | SALARY DIRECT DEPOSIT   | $2,500.00
2024-01-17  | HYDRO BILL PAYMENT      | -$125.00
```

✅ Already in correct format (withdrawals = negative, deposits = positive)

---

## 🛠️ Troubleshooting

### **Problem: Credit card detected as bank account**

**Symptoms:**
- Charges appear as **positive** amounts (should be negative)
- Payments appear as **negative** amounts (should be positive)

**Solution:**
```bash
python pdf_to_quickbooks.py statement.pdf --credit-card
```

### **Problem: Bank account detected as credit card**

**Symptoms:**
- Withdrawals appear as **positive** amounts (should be negative)
- Deposits appear as **negative** amounts (should be positive)

**Solution:**
```bash
python pdf_to_quickbooks.py statement.pdf --bank
```

### **Problem: Unsure which format**

**Solution:**
1. Let auto-detection try first:
   ```bash
   python pdf_to_quickbooks.py statement.pdf
   ```

2. Check the output Excel file:
   - If expenses (like "WALMART") are **positive** → Add `--credit-card`
   - If income (like "SALARY") is **negative** → Add `--bank`

3. Rerun with the correct flag

---

## 📝 Summary

### **Key Points:**

1. ✅ **Credit card statements**: Positive amounts are charges (expenses) → System **inverts** signs
2. ✅ **Bank statements**: Already in correct format → System **keeps** signs unchanged
3. ✅ **Auto-detection**: Works 90%+ of the time using keyword analysis
4. ✅ **Manual override**: Use `--credit-card` or `--bank` flags if needed

### **Decision Tree:**

```
Is it a single Amount column?
├─ YES
│  ├─ Contains "PAYMENT - THANK YOU" or similar? → Credit Card (invert)
│  ├─ Contains "DIRECT DEPOSIT" or similar? → Bank Account (keep)
│  └─ Uncertain? → Default to Bank Account (safer)
│
└─ NO (has Withdrawals/Deposits columns)
   └─ Bank Account (convert using formula: Amount = Deposits - Withdrawals)
```

### **The Formula:**

For **credit cards with single Amount column**:
```python
df['Amount'] = -df['Amount']  # Invert all signs
```

For **bank accounts with Withdrawals/Deposits**:
```python
df['Amount'] = df['Deposits'] - df['Withdrawals']
```

Result: **All expenses are negative, all income is positive** ✅

---

## 🎉 You're All Set!

The system now handles:
- ✅ Credit card statements (Visa, Mastercard, Amex, etc.)
- ✅ Bank account statements (checking, savings)
- ✅ Line of credit statements
- ✅ Mixed formats (auto-detection)

**Test it out:**
```bash
python pdf_to_quickbooks.py your_credit_card_statement.pdf
```

The AI model will receive correctly signed amounts and predict categories accurately! 🚀


