# How the AI Model Expects Credit Card Transactions

## Model Input Format

The AI model expects a DataFrame with these columns:
- **`Date`**: Transaction date (datetime)
- **`Description`**: Transaction description (text)
- **`Amount`**: Transaction amount (numeric)

## Amount Sign Convention

**The model ALWAYS expects the same sign convention, regardless of source:**

- **Negative Amount (`Amount < 0`)**: Expenses (money going out)
- **Positive Amount (`Amount > 0`)**: Income (money coming in)

## Credit Card vs Bank Account

### Bank Account Statements
- **Withdrawals** → Negative amounts (expenses)
- **Deposits** → Positive amounts (income)
- **No conversion needed** - already in correct format

### Credit Card Statements
- **Charges** (purchases) → Must be converted to **Negative** (expenses)
- **Payments** (you paid the card) → Must be converted to **Positive** (income)

**The conversion happens in `_convert_to_standard_format()`:**

```python
# Credit cards show: Positive = Charges (you owe), Negative = Payments (you paid)
# We need: Negative = Expenses (money out), Positive = Income (money in)
# Solution: INVERT the signs for AI processing!
if is_credit_card:
    df['Amount'] = -df['Amount']
```

## Example

**Credit Card PDF shows:**
- `+$100.00` = Purchase at Store (charge)
- `-$50.00` = Payment to card

**After conversion for AI:**
- `-$100.00` = Expense (money out)
- `+$50.00` = Income (money in - you paid off debt)

**Excel output (for user):**
- Amounts are inverted back to original credit card format
- `+$100.00` = Charge
- `-$50.00` = Payment

## Model Features Used

The model uses these features from the transaction:

1. **Date Features:**
   - Year, Month, Day of Week, Is Weekend, Quarter

2. **Amount Features:**
   - `Amount_Abs`: Absolute value of amount
   - `IsIncome`: 1 if Amount > 0, else 0
   - `Amount_Log`: Log of absolute amount
   - `IsHighValue`: 1 if amount > $1000

3. **Description Features:**
   - TF-IDF vectorization of cleaned description text
   - Keywords like "payment", "client", "refund", etc.

4. **Derived Features:**
   - `IsClientPayment`: Contains payment/client keywords
   - `IsRefund`: Contains refund/return keywords

## Key Point

**The model doesn't care if it's a credit card or bank account** - it just needs:
- Negative = expenses (money out)
- Positive = income (money in)

The `_convert_to_standard_format()` function handles the conversion from credit card format to model format.




