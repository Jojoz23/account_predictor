# Bank Statement Processor - How It Works

## 🎯 What This System Does

Automatically converts Canadian bank statement PDFs into categorized Excel/QuickBooks files using AI.

---

## 📋 Complete Pipeline

### **1. Upload (Streamlit UI)**
- User drags & drops PDF bank statements
- Supports: RBC, TD, BMO, Scotiabank, CIBC
- Can process single or multiple files

### **2. PDF Extraction (`extract_bank_statements.py`)**

**What it does:**
- Detects which bank from PDF content
- Extracts all transactions using:
  - **Camelot**: Table-based extraction (best for structured PDFs)
  - **pdfplumber**: Text-based extraction (fallback)
- Parses dates, amounts, descriptions
- Handles edge cases:
  - Multi-line descriptions (combines them)
  - Duplicate detection (keeps legitimate duplicates)
  - Cross-year statements (Dec 2023 → Jan 2024)
  - Different date formats per bank

**Output:**
- DataFrame with: `Date`, `Description`, `Withdrawals`, `Deposits`, `Balance`

### **3. AI Categorization (`pdf_to_quickbooks.py`)**

**What it does:**
- Loads pre-trained neural network model
- For each transaction:
  1. **Text Analysis**: Uses TF-IDF to understand description keywords
  2. **Feature Engineering**: Considers date, amount, patterns
  3. **Prediction**: Assigns QuickBooks account category (28 options)
  4. **Confidence Score**: How certain the AI is (0-100%)

**Example Categories:**
- Sales
- Office Expense
- Bank Charges
- AMA (Alberta Motor Association)
- Meals and Entertainment
- Travel Expense
- etc.

**Output:**
- DataFrame with added: `Account`, `Confidence`

### **4. File Generation**

**Excel File:**
- Human-readable format
- Columns: Date, Description, Debit, Deposit, Account, Confidence
- Multiple sheets: Transactions, Summary, By Account

**QuickBooks IIF File:**
- Text format for QuickBooks Desktop import
- Format: TRNS (transaction) + SPL (split) entries
- Ready to import directly

### **5. User Downloads**

**Single File Mode:**
- 2 files: `categorized_[name].xlsx` + `quickbooks_[name].iif`

**Folder Mode (batch):**
- ZIP file with all Excel + IIF files
- Individual downloads also available

---

## 🔧 Technical Details

### **Streamlit App Structure**

```python
streamlit_app.py
├── main()                     # Main UI layout (tabs, sidebar)
├── process_files()            # Handles PDF processing
│   ├── Initialize AI model
│   ├── Save uploaded PDFs to temp directory
│   ├── For each PDF:
│   │   ├── Extract transactions
│   │   ├── Categorize with AI
│   │   ├── Generate Excel (in memory)
│   │   └── Generate IIF (in memory)
│   └── Store results in session state
└── show_results()             # Display processed data
    ├── Show metrics (confidence breakdown)
    ├── Transaction table with emoji indicators
    ├── Account category breakdown
    └── Download buttons
```

### **Key Design Choices**

1. **Memory Storage**: Files stored in RAM, not disk (security)
2. **Session State**: Preserves data across tab switches
3. **Progress Tracking**: Real-time progress bar during processing
4. **Color Indicators**: Emoji-based (🟢🟡🔴) instead of background colors (easier to read)

---

## 🎨 UI Improvements Made

### **Before:**
- Background colors made text hard to read
- Complex color-coding logic
- Cluttered display

### **After:**
- ✅ Simple emoji indicators (🟢 High, 🟡 Medium, 🔴 Low)
- ✅ Clean white background
- ✅ Clear legend at bottom
- ✅ Simplified column names

---

## 📊 Confidence Scores Explained

### **🟢 High (>80%)**
- AI is very confident
- Usually accurate
- Safe to use as-is

### **🟡 Medium (50-80%)**
- AI is moderately confident
- Quick review recommended
- Often correct but verify

### **🔴 Low (<50%)**
- AI is uncertain
- Manual review needed
- Multiple categories possible

**Example:**
- "AMAZON.CA" → 🟢 "Office Expense" (95% confidence)
- "E-TRANSFER" → 🟡 "Sales" (65% confidence) - could be income or refund
- "Misc Transaction" → 🔴 "Other Expense" (30% confidence) - unclear

---

## 🚀 How to Use

### **Local (Current)**
```bash
streamlit run streamlit_app.py
```
Open browser: http://localhost:8501

### **Deploy to Cloud (Next Step)**
1. Push code to GitHub
2. Go to streamlit.io/cloud
3. Connect repo → Deploy
4. Share URL with users!

---

## 🔐 Security Features

- ✅ Files stored in memory only (no disk storage)
- ✅ Temp files auto-deleted after processing
- ✅ No data sent to external servers (runs locally)
- ✅ Open source code (auditable)

---

## 📝 File Structure

```
account_predictor/
├── streamlit_app.py              # Web UI (this file)
├── pdf_to_quickbooks.py          # AI pipeline
├── extract_bank_statements.py   # PDF extraction
├── models/
│   └── neural_network_account_predictor.pkl  # Trained AI model
├── data/
│   └── Bank Statements/          # Test PDFs
└── requirements.txt              # Python dependencies
```

---

## 🐛 Common Issues & Fixes

**Issue**: "FileNotFoundError" when downloading
- **Fix**: Files now stored in memory (fixed in latest version)

**Issue**: Wrong account categories
- **Fix**: Retrain model with more examples, or manually review low-confidence predictions

**Issue**: Wrong dates extracted
- **Fix**: Year detection improved, handles cross-year statements

**Issue**: Background colors hard to read
- **Fix**: Switched to emoji indicators (🟢🟡🔴)

---

## 🎯 Next Steps

1. ✅ Test with credit card statements
2. ✅ Deploy to Streamlit Cloud (free hosting)
3. ✅ Add user authentication (optional)
4. ✅ Improve AI model with more training data
5. ✅ Add export to CSV, JSON formats

