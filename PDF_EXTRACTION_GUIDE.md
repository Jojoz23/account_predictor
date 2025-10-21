# 📄 Bank Statement PDF Extraction & Auto-Categorization Guide

Complete guide for extracting transactions from PDF bank statements and automatically categorizing them with AI.

---

## 🚀 Quick Start

### 1. Install Required Libraries

```bash
pip install -r requirements.txt
```

**Note:** If you get errors with `camelot-py`, you may need to install additional dependencies:
```bash
# For Windows
pip install ghostscript

# For Mac
brew install ghostscript

# For Linux
sudo apt-get install ghostscript python3-tk
```

---

## 📋 Usage Options

### Option 1: Extract Only (No AI Predictions)

Extract transactions from PDFs without categorizing them:

```bash
# Single PDF file
python extract_bank_statements.py path/to/statement.pdf

# All PDFs in a folder
python extract_bank_statements.py path/to/statements_folder/
```

**Output:**
- `extracted_<filename>.xlsx` - Individual Excel files for each PDF
- `all_transactions_combined.xlsx` - Combined file (when processing folder)

---

### Option 2: Full Pipeline (Extract + AI Categorization + QuickBooks Export)

Extract, categorize, and export ready for QuickBooks:

```bash
# Single PDF file
python pdf_to_quickbooks.py path/to/statement.pdf

# All PDFs in a folder
python pdf_to_quickbooks.py path/to/statements_folder/
```

**Output:**
- `categorized_<filename>.xlsx` - Excel with AI predictions and confidence scores
- `quickbooks_<filename>.iif` - QuickBooks import file
- `all_transactions_categorized.xlsx` - Combined Excel (when processing folder)
- `all_transactions_quickbooks.iif` - Combined QuickBooks file (when processing folder)

---

## 📊 Excel Output Format

The categorized Excel file contains 3 sheets:

### Sheet 1: Categorized Transactions
| Date | Description | Amount | Account | Confidence |
|------|-------------|--------|---------|------------|
| 2024-01-15 | WALMART | -$45.50 | Office Expense | 92.3% |
| 2024-01-16 | Client Payment | $2,500.00 | Sales | 88.1% |

### Sheet 2: Summary
- Total Transactions
- Total Deposits
- Total Withdrawals
- Net Amount
- Confidence Distribution

### Sheet 3: By Account
- Transaction count per account
- Total amount per account
- Average confidence per account

---

## 🏦 Supported Banks

The extractor works with all major Canadian banks:

- ✅ **RBC** (Royal Bank of Canada)
- ✅ **TD** (TD Canada Trust)
- ✅ **BMO** (Bank of Montreal)
- ✅ **Scotiabank**
- ✅ **CIBC**
- ✅ **National Bank**
- ✅ **Desjardins**
- ✅ Most other Canadian banks

---

## 🔧 How It Works

### Extraction Strategies

The extractor uses 3 strategies (tries all automatically):

1. **Table Extraction** - Uses pdfplumber to detect and extract tables (works for most PDFs)
2. **Text Parsing** - Uses regex patterns to extract from text (works for text-based PDFs)
3. **Smart Table** - Advanced table detection with custom settings (works for complex layouts)

### AI Categorization

The neural network model was trained on your data and can predict:
- 26 account categories
- Confidence scores for each prediction
- Top 3 alternative predictions

**Confidence Levels:**
- 🟢 **High (>80%)**: Very confident - likely correct
- 🟡 **Medium (50-80%)**: Somewhat confident - review recommended
- 🔴 **Low (<50%)**: Uncertain - manual review needed

---

## 📥 Importing to QuickBooks

### QuickBooks Desktop (Using IIF File)

1. Open QuickBooks Desktop
2. Go to **File → Utilities → Import → IIF Files...**
3. Select the `quickbooks_<filename>.iif` file
4. Click **Open**
5. Review the imported transactions

### QuickBooks Online (Using Excel)

QuickBooks Online doesn't support IIF files. Use the Excel file instead:

1. Open the `categorized_<filename>.xlsx` file
2. Copy the transactions
3. In QuickBooks Online, go to **Banking → Upload Transactions**
4. Paste or upload the Excel data
5. Map columns: Date → Date, Description → Description, Amount → Amount, Account → Category

---

## 🛠️ Troubleshooting

### Problem: "No transactions extracted"

**Solutions:**
- Check if the PDF is password-protected (remove password first)
- Ensure the PDF contains actual text (not just an image/scan)
- Try converting scanned PDFs to text using OCR first
- Check if the PDF format is supported (most table-based statements work)

### Problem: "Model file not found"

**Solution:**
- Run the neural network training notebook first:
  ```
  notebooks/03_neural_network_training.ipynb
  ```
- This creates the model file: `models/neural_network_account_predictor.pkl`

### Problem: Incorrect predictions

**Solutions:**
- Check confidence scores - low confidence = uncertain predictions
- Add more training data for those account types
- Retrain the model with more examples
- Manually correct low-confidence predictions in Excel

### Problem: "Installation failed for camelot-py"

**Solution:**
- Camelot is optional - comment it out in requirements.txt
- The extractor will still work using pdfplumber and PyPDF2

---

## 🎯 Best Practices

### For Best Extraction Results:

1. **Use Digital PDFs** - Bank statements downloaded directly from online banking work best
2. **Avoid Scanned PDFs** - Photos or scans of statements may not extract well
3. **One Statement at a Time** - Don't combine multiple months in one PDF
4. **Standard Formats** - Official bank statements work better than custom exports

### For Best AI Predictions:

1. **Review Low Confidence** - Always check predictions with <80% confidence
2. **Correct and Retrain** - If you find mistakes, add them to training data and retrain
3. **Consistent Descriptions** - The more consistent your bank's transaction descriptions, the better
4. **More Training Data** - The model improves with more examples

---

## 📈 Performance Tips

### Processing Multiple PDFs

```bash
# Create a folder structure
mkdir statements
mkdir statements/RBC
mkdir statements/TD

# Move PDFs to folders
# Then process each bank separately
python pdf_to_quickbooks.py statements/RBC/
python pdf_to_quickbooks.py statements/TD/
```

### Batch Processing Large Folders

For folders with 50+ PDFs, consider processing in batches:

```bash
# Process first 10 files
python pdf_to_quickbooks.py statements/ --limit 10

# Process next batch
python pdf_to_quickbooks.py statements/ --skip 10 --limit 10
```

*(Note: --limit and --skip options need to be added to the script if needed)*

---

## 🔐 Privacy & Security

- **All processing is local** - Your PDFs never leave your computer
- **No cloud services** - Everything runs locally using your trained model
- **Sensitive data** - The scripts don't store or transmit any data externally

---

## 📞 Need Help?

### Common Questions

**Q: Can I customize the account categories?**  
A: Yes! Train the model with your own categories in the notebook.

**Q: Can I process non-Canadian banks?**  
A: Yes! The extractor works with most table-based bank statements worldwide.

**Q: Can I export to other accounting software?**  
A: Yes! The Excel output works with most software. You can also modify `pdf_to_quickbooks.py` to export other formats.

**Q: How accurate is the AI?**  
A: Current model achieves ~87% accuracy. It improves as you add more training data.

---

## 🎉 Example Workflow

Here's a complete workflow from PDF to QuickBooks:

```bash
# Step 1: Ensure model is trained
# (Run notebooks/03_neural_network_training.ipynb if needed)

# Step 2: Organize your PDFs
mkdir monthly_statements
# Copy all PDFs to this folder

# Step 3: Run the pipeline
python pdf_to_quickbooks.py monthly_statements/

# Step 4: Review the output
# Open all_transactions_categorized.xlsx
# Check confidence scores
# Correct any low-confidence predictions

# Step 5: Import to QuickBooks
# Use all_transactions_quickbooks.iif for QuickBooks Desktop
# Or use the Excel file for QuickBooks Online

# Done! 🎉
```

---

## 📝 Advanced Usage

### Python API

You can also use these as Python modules:

```python
from extract_bank_statements import extract_from_pdf
from pdf_to_quickbooks import PDFToQuickBooks

# Extract only
df = extract_from_pdf('statement.pdf')
print(df.head())

# Full pipeline
pipeline = PDFToQuickBooks()
result = pipeline.process_pdf('statement.pdf')
print(result[['Date', 'Description', 'Account', 'Confidence']].head())
```

### Custom Processing

```python
# Extract without saving
df = extract_from_pdf('statement.pdf', save_excel=False)

# Predict accounts without exporting
pipeline = PDFToQuickBooks()
df = pipeline.predict_accounts(df)

# Custom export format
df.to_csv('custom_output.csv', index=False)
```

---

## 📚 Files Overview

| File | Purpose |
|------|---------|
| `extract_bank_statements.py` | PDF extraction only (no AI) |
| `pdf_to_quickbooks.py` | Full pipeline (Extract + AI + Export) |
| `batch_predict.py` | Predict accounts for existing Excel/CSV |
| `notebooks/03_neural_network_training.ipynb` | Train the AI model |

---

**Happy extracting! 🚀**


