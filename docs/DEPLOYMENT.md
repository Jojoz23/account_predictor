# 🚀 Deployment Guide - Bookeepifier

## Quick Deploy to Streamlit Community Cloud

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit - Bookeepifier app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

### Step 2: Deploy on Streamlit
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click "New app"
3. Connect your GitHub repository
4. Set:
   - **Repository**: `YOUR_USERNAME/YOUR_REPO_NAME`
   - **Branch**: `main`
   - **Main file path**: `streamlit_app.py`
5. Click "Deploy!"

### Step 3: Your app will be live at:
`https://YOUR_APP_NAME.streamlit.app`

## 📋 Requirements
- Python 3.8+
- All dependencies in `requirements.txt`
- Model file: `models/neural_network_account_predictor.pkl`

## 🔧 Environment Variables (if needed)
No environment variables required - everything is self-contained!

## 📁 Files Included in Deployment
- ✅ `streamlit_app.py` - Main app (repo root)
- ✅ `pdf_to_quickbooks.py` - Processing pipeline
- ✅ `extract_bank_statements.py` - PDF extraction
- ✅ `models/neural_network_account_predictor.pkl` - AI model
- ✅ `requirements.txt` - Dependencies
- ✅ `README.md` - Documentation

## 🎯 App Features
- Upload PDF bank statements (RBC, TD, BMO, Scotiabank, CIBC)
- AI-powered transaction categorization
- Export to Excel and QuickBooks IIF formats
- Batch processing for multiple files
- File reordering for batch mode
