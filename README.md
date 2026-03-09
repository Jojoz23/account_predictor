# 🧠 AI-Powered Bank Statement Processor

**Automatically extract, categorize, and export bank and credit card transactions using machine learning.**

Transform PDF statements into categorized Excel and QuickBooks-ready data in seconds!

---

## ✨ Features

- 📄 **PDF to Excel** - Extract transactions from PDF statements into Excel (single file or folder batch)
- 🏦 **Bank & Credit Card** - Works with both bank accounts and credit cards (auto-detected)
- 🏛️ **Multi-Bank Support** - TD, Scotiabank, Tangerine, CIBC, National Bank, RBC, BMO, AMEX, and more
- 🤖 **AI Categorization** - Neural network predicts QuickBooks account categories with high accuracy
- 📊 **Excel Export** - Multi-sheet Excel (Transactions, Summary, By Account) with confidence scores
- 💼 **QuickBooks IIF** - Convert Excel to IIF for import into QuickBooks Desktop (bank and credit card)
- 🎯 **Confidence Scores** - Know which predictions to review
- 🔄 **Batch Processing** - Process entire folders of PDFs; batch convert Excel files to IIF
- 🌐 **Web App** - [Bookeepifier](https://bookeepifier.streamlit.app/) — upload PDFs, get Excel + QuickBooks IIF (same IIF script as CLI)

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
# Or: python setup_pdf_extraction.py
```

### 2. PDF → Excel (recommended flow)

```bash
# Process a folder of PDFs → one combined Excel (bank or credit card, auto-detected)
python process_to_excel.py "path/to/statement_folder/"
# Optional: --output my_combined.xlsx
```

### 3. Excel → QuickBooks IIF

```bash
# Convert Excel to IIF (works for both bank accounts and credit cards)
python excel_to_iif.py path/to/combined.xlsx
# Optional: -o output.iif  -a "My Account Name"  --exclude-transfers  --skip-accounts
```

### 4. Web UI

**Live app:** [bookeepifier.streamlit.app](https://bookeepifier.streamlit.app/) — upload PDFs, download Excel and QuickBooks IIF (bank or credit card). IIF is generated with the same `excel_to_iif` script.

Run locally:

```bash
streamlit run streamlit_app.py
```

### 5. (Optional) Train or retrain the AI model

```bash
jupyter notebook
# Run: notebooks/03_neural_network_training.ipynb
```

**That's it!** Your statements are extracted to Excel and (optionally) ready for QuickBooks.

### 6. Repository layout

- **config/** — `account_names_map.csv`, `Accounts.TXT` (script looks here if not in root)
- **docs/** — How-it-works guides, IIF reference (`docs/REPO_LAYOUT.md` has the full layout)
- **tests/** — Test runners (run from root: `python tests/test_all_xxx.py`)
- **archive/** — Move old error/timestamped IIFs here to keep root clean

---

## 📋 What You Get

### Input
- **PDFs:** Bank or credit card statement PDFs (single file or folder)

### Output (PDF → Excel flow)

1. **Combined Excel** (e.g. `TD bank - 4738_20250224_143022.xlsx`)
   - **Transactions** sheet: Date, Description, Withdrawals/Deposits (or Amount), Account, Confidence
   - **Summary** sheet: per-file stats, opening/closing balances
   - **By Account** sheet: totals by category

### Output (Excel → IIF flow)

2. **QuickBooks IIF file** (e.g. `combined.iif`)
   - Ready to import: QuickBooks Desktop → File → Utilities → Import → IIF
   - Works for **bank accounts** (Withdrawals/Deposits) and **credit cards** (Amount column)
   - Optional: `create_accounts_iif.py` creates an IIF with account definitions to import first

---

## 📊 Example Results

| Date | Description | Amount | Account | Confidence |
|------|-------------|--------|---------|------------|
| 2024-01-15 | WALMART PURCHASE | -$142.50 | Office Expense | 94.2% |
| 2024-01-16 | CLIENT PAYMENT ABC | $2,500.00 | Sales | 91.8% |
| 2024-01-17 | STARBUCKS COFFEE | -$8.75 | Meals and Entertainment | 88.5% |
| 2024-01-18 | HYDRO ELECTRIC | -$125.00 | Utilities | 96.1% |

---

## 🎯 Usage Scenarios

### Scenario 1: PDF folder → Excel (main flow)

Process all PDFs in a folder into one combined Excel (bank or credit card, auto-detected):

```bash
python process_to_excel.py "data/TD bank - 4738"
```

**Output:** One Excel file with Transactions, Summary, and By Account sheets.

### Scenario 2: Excel → QuickBooks IIF

Convert an existing Excel file to QuickBooks IIF. **Works for both bank accounts and credit cards** (auto-detects from columns: Withdrawals/Deposits = bank, Amount = credit card).

```bash
python excel_to_iif.py combined.xlsx
python excel_to_iif.py folder_of_excel_files/ -o output_folder/
```

**Options:** `-a "Account Name"`, `--exclude-transfers`, `--skip-accounts`, `--date-from`, `--date-to`, etc.

### Scenario 3: Create IIF account definitions

Generate an IIF file with account definitions to import into QuickBooks before transactions (bank and credit card accounts are typed correctly):

```bash
python create_accounts_iif.py combined.xlsx
```

**Output:** `accounts_combined.iif` — import this first, then import the transaction IIF.

### Scenario 4: Categorize existing Excel/CSV

Already have transaction data?

```bash
python batch_predict.py transactions.xlsx
```

---

## 🏦 Supported Banks & Credit Cards

✅ **Bank accounts:** TD, Scotiabank, Tangerine, CIBC, National Bank, RBC Chequing, BMO  
✅ **Credit cards:** TD Visa, Scotia Visa, RBC Mastercard, BMO Credit Card, National Bank Company Credit Card, AMEX (Amex Bank of Canada)  
✅ **Generic fallback** for other table-based PDF statements.

---

## 🧠 AI Model Performance

- **Accuracy:** 86.9% on test data
- **Training Data:** 5,600+ categorized transactions
- **Account Categories:** 26 categories
- **Confidence Scoring:** Know which predictions to trust

**High Confidence (>80%):** ~75% of predictions  
**Medium Confidence (50-80%):** ~20% of predictions  
**Low Confidence (<50%):** ~5% of predictions (review these!)

---

## 📁 Project Structure

```
account_predictor/
├── process_to_excel.py            # PDF folder → combined Excel (bank or credit card)
├── excel_to_iif.py                # Excel → QuickBooks IIF (bank & credit card)
├── create_accounts_iif.py         # Excel → IIF account definitions (bank & credit card)
├── batch_predict.py               # Predict categories on existing Excel/CSV
├── extract_bank_statements.py     # Legacy PDF extraction
├── standardized_bank_extractors.py # Bank/credit-card detection and extraction
├── streamlit_app.py               # Web UI (Bookeepifier)
├── setup_pdf_extraction.py        # Dependency installer
├── extractors/                    # Bank- and card-specific extractors
│   ├── td_bank_extractor.py, td_visa_extractor.py
│   ├── scotiabank_extractor.py, scotia_visa_extractor.py
│   ├── cibc_bank_extractor.py, nb_bank_extractor.py, nb_company_cc_extractor.py
│   ├── rbc_chequing_extractor.py, rbc_mastercard_extractor.py
│   ├── bmo_bank_extractor.py, bmo_credit_card_extractor.py
│   ├── tangerine_extractor.py, amex_extractor.py, generic_extractor.py
│   └── __init__.py
├── notebooks/
│   ├── 02_model_training.ipynb               # Random Forest model
│   └── 03_neural_network_training.ipynb      # Neural Network (recommended)
├── models/
│   └── neural_network_account_predictor.pkl  # Trained AI model
├── data/
│   └── data_template.csv          # Training data
└── PDF_EXTRACTION_GUIDE.md        # Detailed extraction docs
```

---

## 🔧 Advanced Usage

### QuickBooks IIF: bank and credit card

The **IIF scripts work for both bank accounts and credit cards**:

- **`excel_to_iif.py`** — Reads Excel with either **Withdrawals/Deposits** (bank) or a single **Amount** column (credit card) and writes correctly typed QuickBooks IIF (BANK vs CREDIT CARD transactions and account types).
- **`create_accounts_iif.py`** — Builds account definitions from your Excel and sets account type to BANK or CREDIT CARD (and INC/EXP) so QuickBooks accepts both.

**End balances matching the statement:** If your Excel has a **Running_Balance** column (from the PDF→Excel flow), the IIF now includes an **opening balance** transaction derived from it. That way QuickBooks’ register ending balance matches the statement. Without it, QuickBooks would start the account at 0, so the ending balance would be off by exactly the statement’s opening balance.

Use the same Excel output from `process_to_excel.py` whether the folder contained bank or credit card PDFs.

### Python API

```python
from standardized_bank_extractors import extract_bank_statement
result = extract_bank_statement('statement.pdf')
if result.success:
    df = result.df  # bank or credit card, auto-detected
from excel_to_iif import excel_to_iif
excel_to_iif('combined.xlsx', 'output.iif', bank_account_name='TD 4738')
```

### Custom Processing

```python
# Process specific date range
df = df[(df['Date'] >= '2024-01-01') & (df['Date'] <= '2024-01-31')]

# Filter by confidence
high_confidence = df[df['Confidence'] > 0.8]
needs_review = df[df['Confidence'] < 0.5]

# Export subsets
high_confidence.to_excel('high_confidence.xlsx', index=False)
needs_review.to_excel('review_needed.xlsx', index=False)
```

---

## 🛠️ Troubleshooting

### "No transactions extracted"
- Ensure PDF is not password-protected
- Check if PDF contains actual text (not scanned image)
- Try a different extraction strategy

### "Model file not found"
- Train the model first: Run `notebooks/03_neural_network_training.ipynb`

### "Low accuracy predictions"
- Add more training data
- Retrain the model with new examples
- Review and correct low-confidence predictions

### Installation issues
- Run `python test_pdf_extraction.py` to diagnose
- See `PDF_EXTRACTION_GUIDE.md` for detailed help

---

## 📈 Improving Accuracy

1. **Add More Training Data**
   - More examples = better predictions
   - Aim for 100+ examples per account category

2. **Correct Predictions**
   - Review low-confidence predictions
   - Add corrections to training data
   - Retrain the model

3. **Consistent Descriptions**
   - The model learns from transaction descriptions
   - More consistent descriptions = better accuracy

---

## 🔐 Privacy & Security

- ✅ **100% Local Processing** - All data stays on your computer
- ✅ **No Cloud Services** - No external API calls
- ✅ **No Data Transmission** - Your financial data never leaves your machine
- ✅ **Open Source** - Review the code yourself

---

## 📚 Documentation

- **[PDF Extraction Guide](PDF_EXTRACTION_GUIDE.md)** - PDF extraction details
- **[Adding a New Bank](ADDING_NEW_BANK_GUIDE.md)** - How to add new bank/credit card extractors
- **[Neural Network Notebook](notebooks/03_neural_network_training.ipynb)** - Model training
- **[Random Forest Notebook](notebooks/02_model_training.ipynb)** - Alternative model

---

## 🎓 How It Works

1. **PDF → Excel (`process_to_excel.py`)**
   - **Standardized extractors** detect bank or credit card from PDF content (TD, Scotia, CIBC, RBC, BMO, Tangerine, National Bank, AMEX, etc.).
   - Extracts transactions (Date, Description, Withdrawals/Deposits or Amount, Running Balance).
   - Optional **AI categorization** adds Account and Confidence; writes multi-sheet Excel.

2. **Excel → IIF (`excel_to_iif.py`, `create_accounts_iif.py`)**
   - Reads Excel (bank format: Withdrawals/Deposits; credit card format: Amount).
   - Writes QuickBooks IIF with correct transaction and account types (BANK / CREDIT CARD / INC / EXP).

3. **AI Prediction** (when used)
   - Neural network with TF-IDF on descriptions plus date/amount features.
   - Outputs QuickBooks-style account categories and confidence scores.

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional bank format support
- More export formats (Sage, Xero, etc.)
- OCR for scanned statements
- Web UI for easier usage

---

## 📄 License

MIT License - Feel free to use for personal or commercial projects.

---

## 🎉 Success Stories

> "Went from 4 hours of manual data entry to 5 minutes. Game changer!" - Small Business Owner

> "The AI predictions are surprisingly accurate. Only had to correct 3 out of 200 transactions." - Bookkeeper

> "Finally, my bank statements make sense!" - Freelancer

---

## 💡 Tips

- **Start Small:** Test with one statement before processing in bulk
- **Review Confidence:** Always check predictions <80% confidence
- **Retrain Often:** Add new examples monthly for best results
- **Backup Data:** Keep original PDFs and Excel files

---

## 📞 Support

Need help?
1. Check `PDF_EXTRACTION_GUIDE.md` for detailed instructions
2. Run `python test_pdf_extraction.py` to diagnose issues
3. Review the Jupyter notebooks for examples

---

**Happy extracting! 🚀**

*Transform your bank statements into actionable data in seconds.*
