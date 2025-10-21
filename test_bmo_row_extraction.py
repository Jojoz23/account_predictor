from extract_bank_statements import BankStatementExtractor
import camelot

pdf_path = 'data/1. Jan 31st 2022.pdf'

extractor = BankStatementExtractor(pdf_path)
tables = camelot.read_pdf(pdf_path, pages='1', flavor='stream')
df = tables[0].df

print("=== Testing BMO Row Extraction ===\n")

# Test extracting Row 3
row3 = [str(cell).strip() for cell in df.iloc[3].tolist()]
print(f"Row 3: {row3}")
print(f"Number of columns: {len(row3)}")

# Try to extract
transaction = extractor._extract_transaction_from_row_with_date(row3, 'Jan 04')

print(f"\nExtraction result: {transaction}")

if not transaction:
    print("\n❌ Failed to extract. Let me trace through the logic...")
    print(f"\nRow has {len(row3)} columns (BMO has 4, RBC has 5+)")
    print(f"Date: {row3[0]}")
    print(f"Description: {row3[1]}")
    print(f"Amount (col 2): {row3[2]}")
    print(f"Balance (col 3): {row3[3]}")
    
    # The issue is likely in _extract_transaction_from_row
    # which checks if len(row) >= 4 but then looks for amounts in wrong columns


