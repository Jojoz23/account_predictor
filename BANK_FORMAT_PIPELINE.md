# Bank Statement Format Integration Pipeline

This document outlines the standardized pipeline for adding support for new bank statement formats.

## Pipeline Steps

### 1. **Initial Testing Scripts**
   - Create test scripts to understand how the current system works on the new bank format
   - Test with a single PDF first
   - Identify what works and what doesn't
   - **Script naming**: `test_[bank]_single.py`, `test_[bank]_current.py`
   - **Goal**: Understand the current behavior and identify gaps

### 2. **Targeted Debug Scripts**
   - Create focused debug scripts to fix specific issues:
     - Year extraction (`test_[bank]_year.py`)
     - Opening/ending balance extraction (`debug_[bank]_balance.py`)
     - Transaction parsing (`debug_[bank]_transactions.py`)
     - Balance verification (`test_[bank]_balance_verification.py`)
   - Fix issues one at a time
   - Verify each fix independently
   - **Goal**: Fix individual components before integrating

### 3. **Batch Testing**
   - Run extraction on all available statements for the new bank
   - Generate individual Excel files per PDF
   - Create summary report with:
     - Transaction counts
     - Opening/closing balances
     - Success/failure status
     - Any errors encountered
   - **Script naming**: `test_all_[bank].py`
   - **Goal**: Ensure consistency across all statements

### 4. **Full Pipeline Integration**
   - Update `extract_bank_statements.py` with bank-specific logic
   - Ensure changes are scoped to the new bank only (don't break existing banks)
   - Update `pdf_to_quickbooks.py` if needed
   - Test the full pipeline on the bank's folder
   - **Goal**: Integrate fixes into main codebase

### 5. **Final Verification**
   - Run full pipeline on all statements
   - Verify:
     - Excel date formats are correct
     - Opening/closing balances match PDFs
     - Transaction counts are accurate
     - Running balances are correct
     - No regressions in other banks
   - **Goal**: Confirm everything works end-to-end

## Best Practices

### Code Organization
- **Bank-specific logic**: Use conditional checks like `if bank == 'NEWBANK':`
- **Helper functions**: Create bank-specific helpers (e.g., `_parse_camelot_transactions_newbank()`)
- **Metadata storage**: Store bank-specific data in `self.metadata` (e.g., `newbank_opening_balance`)

### Testing Strategy
- **Start small**: Test one PDF before batch testing
- **Incremental fixes**: Fix one issue at a time
- **Print statements**: Use detailed logging during debugging
- **Compare outputs**: Compare working vs non-working PDFs

### Debugging Tips
- Use `print()` statements liberally during development
- Check DataFrame contents at each step
- Verify column indices and header detection
- Test edge cases (empty cells, multiline descriptions, etc.)

## Example: Scotiabank Integration

1. **Initial Testing**: `test_scotiabank_single.py` - tested current system
2. **Targeted Debug**: 
   - `test_year_extraction.py` - fixed year extraction
   - `debug_scotiabank_extraction_logic.py` - fixed transaction parsing
   - `test_scotiabank_summary.py` - verified balances
3. **Batch Testing**: `test_all_scotia_business.py` - tested all PDFs
4. **Full Pipeline**: Updated `extract_bank_statements.py` with Scotiabank-specific logic
5. **Verification**: Ran `pdf_to_quickbooks.py` on entire folder, verified Excel outputs

## Checklist for New Bank Format

- [ ] Create initial test script
- [ ] Identify what works/doesn't work
- [ ] Create targeted debug scripts for:
  - [ ] Year extraction
  - [ ] Opening balance
  - [ ] Closing balance
  - [ ] Transaction parsing
  - [ ] Balance verification
- [ ] Fix issues one by one
- [ ] Create batch test script
- [ ] Run on all available statements
- [ ] Integrate fixes into main codebase
- [ ] Test full pipeline
- [ ] Verify Excel outputs
- [ ] Ensure no regressions in other banks
- [ ] Commit and push changes




