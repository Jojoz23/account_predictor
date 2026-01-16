# Guide: Adding a New Bank to the Standardized Extractors System

This guide outlines the step-by-step process for adding support for a new bank or credit card statement format.

---

## Overview

When adding a new bank, you'll go through these stages:
1. **Exploration** - Understand the PDF structure
2. **Test Script** - Create standalone extraction script
3. **Folder Testing** - Test on all PDFs in the folder
4. **Extractor Class** - Integrate into standardized system
5. **Verification** - Ensure output matches test script

---

## Stage 1: Exploration

**Purpose:** Understand the PDF structure, table layout, and data extraction points.

**Reference Files:**
- `explore_cibc_cad.py` - Bank account example
- `explore_cibc_visa.py` - Credit card example
- `explore_scotia_personal_cc.py` - Another credit card example

**Steps:**
1. Create `explore_<bank>_<account_type>.py` script
2. Use `pdfplumber` to extract text and inspect structure
3. Use `camelot` (stream flavor) to find transaction tables
4. Identify:
   - Statement period format
   - Account number location
   - Opening/closing balance patterns
   - Transaction table structure (headers, date columns, amount columns)
   - Page numbers where transactions appear

**Key Patterns to Identify:**
- Date formats (e.g., "Dec 25", "12/25/2024", "2024-12-25")
- Amount formats (with/without $, negative indicators)
- Description column location
- Balance calculation method
- Multi-page transaction tables

**Example Command:**
```bash
python explore_nb_cad.py
```

---

## Stage 2: Create Test Script

**Purpose:** Build a standalone extraction function that can process one PDF file.

**Reference Files:**
- `test_cibc_cad_complete.py` - Bank account example
- `test_cibc_usd_complete.py` - Multi-currency example
- `test_td_visa_complete.py` - Credit card example

**File Naming:** `test_<bank>_<account_type>_complete.py`

**Structure:**
```python
def extract_<bank>_<account_type>_statement(pdf_path: str):
    """
    Extract transactions from <Bank> <Account Type> statement
    
    Returns:
    - df: DataFrame with Date, Description, Amount/Withdrawals/Deposits, Running_Balance
    - opening_balance: float or None
    - closing_balance: float or None
    - statement_year: str or None
    """
    # Implementation here
    return df, opening_balance, closing_balance, statement_year

if __name__ == "__main__":
    # Test on first file
    pdf_dir = Path("data/...")
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    df, opening, closing, year = extract_<bank>_<account_type>_statement(str(pdf_files[0]))
    print(df)
```

**Important Considerations:**
- **Credit Cards:** Use `Amount` column (positive = charges, negative = payments)
- **Bank Accounts:** Use `Withdrawals` and `Deposits` columns separately
- **Date Format:** Return dates as strings in 'YYYY-MM-DD' format
- **Running Balance:** Calculate from opening balance + cumulative transactions
- **Year Logic:** Handle statements spanning two calendar years (e.g., Dec 2024 - Jan 2025)

**Example Command:**
```bash
python test_nb_cad_complete.py
```

---

## Stage 3: Test on Full Folder

**Purpose:** Verify extraction works on all PDFs in the folder and identify edge cases.

**Reference Files:**
- `test_all_cibc_cad.py` - Example folder testing script
- `test_all_cibc_usd.py` - Another example

**File Naming:** `test_all_<bank>_<account_type>.py`

**Structure:**
```python
def test_all_files(folder_path):
    pdf_files = sorted(Path(folder_path).glob("*.pdf"))
    
    for pdf_file in pdf_files:
        print(f"\nTesting: {pdf_file.name}")
        df, opening, closing, year = extract_<bank>_<account_type>_statement(str(pdf_file))
        
        # Validate
        print(f"  Transactions: {len(df)}")
        print(f"  Opening: ${opening:,.2f}" if opening else "  Opening: None")
        print(f"  Closing: ${closing:,.2f}" if closing else "  Closing: None")
        
        # Check running balance matches closing balance
        if len(df) > 0 and closing is not None:
            final_rb = df['Running_Balance'].iloc[-1]
            diff = abs(final_rb - closing)
            if diff < 0.01:
                print(f"  ✅ Balance match!")
            else:
                print(f"  ⚠️  Balance difference: ${diff:,.2f}")

if __name__ == "__main__":
    test_all_files("data/<Bank Folder>")
```

**What to Check:**
- All files process successfully
- Running balance matches closing balance for each file
- No transactions are missed
- Dates are correct (especially for cross-year statements)
- Amounts are correct (signs, decimal places)

**Example Command:**
```bash
python test_all_nb_cad.py
```

---

## Stage 4: Create Extractor Class

**Purpose:** Integrate the extraction function into the standardized system.

**Reference Files:**
- `extractors/cibc_bank_extractor.py` - Bank account extractor example
- `extractors/scotia_visa_extractor.py` - Credit card extractor example
- `extractors/td_bank_extractor.py` - Another bank account example

**File Location:** `extractors/<bank>_<account_type>_extractor.py`

**Structure:**
```python
"""<Bank> <Account Type> Extractor Implementation"""

import pandas as pd
from standardized_bank_extractors import BankExtractorInterface, ExtractionResult, standardize_dataframe

# Import or copy your extraction function
from test_<bank>_<account_type>_complete import extract_<bank>_<account_type>_statement

class <Bank><AccountType>Extractor(BankExtractorInterface):
    """Extractor for <Bank> <Account Type> statements"""
    
    def detect_bank(self, pdf_path: str) -> bool:
        """Check if PDF is a <Bank> <Account Type> statement"""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ""
                text_lower = text.lower()
                
                # Add detection logic
                has_bank = '<bank keyword>' in text_lower
                has_account_type = '<account type keyword>' in text_lower
                
                # Make sure it's not a different bank/type
                is_not_other = '<other bank>' not in text_lower
                
                return has_bank and has_account_type and is_not_other
        except:
            return False
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """Extract <Bank> <Account Type> statement"""
        try:
            # Call extraction function
            df, opening_balance, closing_balance, statement_year = extract_<bank>_<account_type>_statement(pdf_path)
            
            # Standardize DataFrame
            is_credit_card = <True/False>  # Set based on account type
            df_standardized = standardize_dataframe(df, is_credit_card=is_credit_card)
            
            # Create metadata
            metadata = {
                'bank': '<Bank Name>',
                'is_credit_card': is_credit_card,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'statement_year': str(statement_year) if statement_year else None,
                'extraction_method': 'camelot'  # or 'pdfplumber'
            }
            
            # Update Running_Balance with opening balance if available
            if opening_balance is not None and not df_standardized.empty:
                if is_credit_card:
                    df_standardized['Running_Balance'] = opening_balance + df_standardized['Amount'].cumsum()
                else:
                    df_standardized['Running_Balance'] = opening_balance + (df_standardized['Deposits'].fillna(0) - df_standardized['Withdrawals'].fillna(0)).cumsum()
            
            return ExtractionResult(
                df=df_standardized,
                metadata=metadata,
                success=True
            )
        except Exception as e:
            return ExtractionResult(
                df=pd.DataFrame(),
                metadata={'bank': '<Bank Name>', 'is_credit_card': is_credit_card},
                success=False,
                error=str(e)
            )
```

**Key Points:**
- Detection logic must be specific enough to avoid false positives
- Set `is_credit_card` correctly (affects standardization)
- Ensure `Running_Balance` is calculated with opening balance
- Handle errors gracefully

---

## Stage 5: Integrate into Standardized System

**Purpose:** Add the extractor to the orchestrator so it's automatically used.

**Reference Files:**
- `standardized_bank_extractors.py` - Main orchestrator file
- `extractors/__init__.py` - Package exports

**Steps:**

### 5.1 Update `extractors/__init__.py`

Add your extractor to the exports:
```python
from .<bank>_<account_type>_extractor import (
    <Bank><AccountType>Extractor,
    extract_<bank>_<account_type>_statement,
)

__all__ = [
    # ... existing exports ...
    '<Bank><AccountType>Extractor',
    'extract_<bank>_<account_type>_statement',
]
```

### 5.2 Update `standardized_bank_extractors.py`

**A. Add imports:**
```python
from extractors import (
    # ... existing imports ...
    <Bank><AccountType>Extractor,
    extract_<bank>_<account_type>_statement,
)
```

**B. Add to `__all__`:**
```python
__all__ = [
    # ... existing exports ...
    '<Bank><AccountType>Extractor',
    'extract_<bank>_<account_type>_statement',
]
```

**C. Add to `BankExtractorOrchestrator.__init__()`:**
```python
def __init__(self):
    self.extractors = [
        # ... existing extractors ...
        <Bank><AccountType>Extractor(),  # Add here (order matters!)
        GenericExtractor()  # Always last
    ]
```

**Important:** Order matters! Credit card extractors should come before bank account extractors for the same bank (e.g., Scotia Visa before Scotiabank).

**D. Add to `get_extractor_for_bank()` method:**
```python
def get_extractor_for_bank(self, bank_name: str):
    bank_lower = bank_name.lower()
    
    # ... existing conditions ...
    elif '<bank>' in bank_lower and '<account_type>' in bank_lower:
        return <Bank><AccountType>Extractor()
    elif '<bank>' in bank_lower:
        return <Bank><AccountType>Extractor()  # or generic bank extractor
```

---

## Stage 6: Verification

**Purpose:** Ensure the standardized extractor produces the same output as your test script.

**Reference Files:**
- `test_standardized_extractors.py` - Comparison test framework

**Steps:**

### 6.1 Add Test Function to `test_standardized_extractors.py`

```python
def test_<bank>_<account_type>(pdf_path: str, verbose: bool = False):
    """Test <Bank> <Account Type> extraction"""
    print(f"\n{'='*80}")
    print(f"Testing: {Path(pdf_path).name}")
    print(f"{'='*80}\n")
    
    # 1. Run original extraction (test script)
    from test_<bank>_<account_type>_complete import extract_<bank>_<account_type>_statement
    df_original, opening_orig, closing_orig, year_orig = extract_<bank>_<account_type>_statement(pdf_path)
    
    # 2. Run standardized extraction
    from standardized_bank_extractors import extract_bank_statement
    result = extract_bank_statement(pdf_path)
    df_standardized = result.df
    opening_std = result.metadata.get('opening_balance')
    closing_std = result.metadata.get('closing_balance')
    
    # 3. Compare
    differences = compare_dataframes(df_original, df_standardized, "Original", "Standardized")
    
    # 4. Validate balances match
    # ... (see test_standardized_extractors.py for examples)
    
    return differences
```

### 6.2 Add to Test Config

In `test_standardized_extractors.py`, add to `test_configs`:
```python
test_configs = [
    # ... existing configs ...
    {
        'name': '<Bank> <Account Type>',
        'folder': Path('data/<Bank Folder>'),
        'test_func': test_<bank>_<account_type>,
    },
]
```

### 6.3 Run Tests

```bash
# Test specific bank
python test_standardized_extractors.py --<bank> --verbose

# Test all
python test_standardized_extractors.py
```

**What to Verify:**
- Number of transactions matches
- Opening/closing balances match
- Transaction amounts match (within 0.01 tolerance)
- Dates match exactly
- Running balances match
- Column structure matches expected format

---

## Stage 7: Generate Excel Files

**Purpose:** Use the centralized Excel processor to generate combined files.

**Reference Files:**
- `process_to_excel.py` - Centralized Excel processor

**Usage:**
```bash
python process_to_excel.py "data/<Bank Folder>"
```

**The script will automatically:**
- Detect bank type using standardized extractors
- Extract all transactions
- Predict account categories (AI model)
- Generate multi-sheet Excel file (Transactions, Summary, By Account)
- Validate running balances match closing balances

**Output:**
- Excel file in `data/` folder with timestamp
- Format: `<Folder_Name>_combined_YYYYMMDD_HHMMSS.xlsx`

---

## Checklist Summary

- [ ] Created exploration script (`explore_<bank>_<type>.py`)
- [ ] Identified PDF structure and transaction table locations
- [ ] Created test extraction script (`test_<bank>_<type>_complete.py`)
- [ ] Tested on single file successfully
- [ ] Created folder test script (`test_all_<bank>_<type>.py`)
- [ ] All files in folder process correctly
- [ ] Running balances match closing balances
- [ ] Created extractor class (`extractors/<bank>_<type>_extractor.py`)
- [ ] Detection logic correctly identifies bank/type
- [ ] Updated `extractors/__init__.py`
- [ ] Updated `standardized_bank_extractors.py` (imports, exports, orchestrator)
- [ ] Added test to `test_standardized_extractors.py`
- [ ] Verification tests pass (output matches test script)
- [ ] Generated Excel file using `process_to_excel.py`
- [ ] Excel file format is correct (columns, dates, amounts)

---

## Common Issues and Solutions

### Issue: Detection Logic False Positives
**Solution:** Make detection more specific. Check for multiple keywords and exclude other banks.

### Issue: Running Balance Doesn't Match Closing Balance
**Solution:** 
- Verify opening balance extraction
- Check transaction order (preserve original order within same date)
- Verify amount signs (withdrawals negative, deposits positive for bank accounts)

### Issue: Dates Wrong for Cross-Year Statements
**Solution:** Implement year logic based on statement period (e.g., Dec 2024 = 2024, Jan 2025 = 2025).

### Issue: Some Transactions Missing
**Solution:** 
- Check if transactions span multiple pages
- Verify table detection (may need to try different Camelot flavors)
- Check for multi-line descriptions that might be split

### Issue: Excel Output Shows Time in Dates
**Solution:** Already handled in `process_to_excel.py` - dates are converted to date-only format.

---

## Notes

- **Keep test scripts:** Don't delete `test_<bank>_<type>_complete.py` - they're referenced by extractors
- **Exploration scripts:** Can be kept for reference or deleted (not used by system)
- **Order matters:** Credit card extractors must come before bank account extractors in orchestrator
- **Standardization:** Always use `standardize_dataframe()` in extractor class
- **Error handling:** Always return `ExtractionResult` with proper error messages

---

## Examples of Complete Implementations

- **CIBC Bank (CAD/USD):** `extractors/cibc_bank_extractor.py`
- **Scotia Visa:** `extractors/scotia_visa_extractor.py`
- **TD Bank:** `extractors/td_bank_extractor.py`

Refer to these files for complete working examples.
