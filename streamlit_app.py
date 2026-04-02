"""
Bank Statement PDF to Excel & QuickBooks IIF - Streamlit Web App

1. Upload PDFs (bank or credit card) → extraction + AI categorization
2. Download Excel and QuickBooks IIF (IIF generated via excel_to_iif script; works for bank and credit card)
"""

import sys
from pathlib import Path

# pdf_to_quickbooks lives in scripts/; other deps are at repo root
_ROOT = Path(__file__).resolve().parent
_SCRIPTS = _ROOT / "scripts"
for _p in (_ROOT, _SCRIPTS):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import streamlit as st
import pandas as pd
import tempfile
import contextlib
from pdf_to_quickbooks import PDFToQuickBooks
from standardized_bank_extractors import extract_bank_statement
from excel_to_iif import excel_to_iif
import io

# Page configuration
st.set_page_config(
    page_title="Bookeepifier",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Keep header + main menu visible so users can open Settings → Theme (light / dark / system).
# Only hide the footer “Made with Streamlit” strip.
hide_streamlit_style = """
<style>
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Simple, clean application with confidence indicators
st.markdown("""
<style>
    .confidence-high {
        color: #22c55e;
        font-weight: 600;
    }
    .confidence-medium {
        color: #eab308;
        font-weight: 600;
    }
    .confidence-low {
        color: #f97316;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = []
if 'is_batch_mode' not in st.session_state:
    st.session_state.is_batch_mode = False
if 'file_order' not in st.session_state:
    st.session_state.file_order = []
if 'excel_iif_result' not in st.session_state:
    st.session_state.excel_iif_result = None
if 'excel_iif_filename' not in st.session_state:
    st.session_state.excel_iif_filename = None

def _generate_iif_from_dataframe(df, bank_account_name="Bookeepifier Statements"):
    """Generate QuickBooks IIF content from a dataframe using excel_to_iif script (bank or credit card)."""
    with tempfile.TemporaryDirectory() as d:
        temp_excel = Path(d) / "temp.xlsx"
        temp_iif = Path(d) / "temp.iif"
        cols = ["Date", "Description", "Account"]
        if "Amount" in df.columns:
            cols.insert(2, "Amount")
        else:
            cols.extend(["Withdrawals", "Deposits"])
        export_df = df[[c for c in cols if c in df.columns]].copy()
        export_df.to_excel(temp_excel, index=False, sheet_name="Transactions")
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = excel_to_iif(
                str(temp_excel),
                str(temp_iif),
                bank_account_name=bank_account_name,
                skip_account_definitions=True,
            )
        if result and temp_iif.exists():
            return temp_iif.read_text(encoding="utf-8")
    return None

def main():
    # Header
    st.title("Bookeepifier")
    st.markdown("Upload PDF bank or credit card statements → AI categorizes → Download Excel & QuickBooks IIF")
    
    st.divider()
    
    # Always use auto-detect mode
    is_credit_card = None
    
    # File uploader
    st.header("Upload Bank Statements")
    
    # File uploader (with dynamic key for clearing)
    uploader_key = st.session_state.get('uploader_key', 'main_uploader')
    
    uploaded_files = st.file_uploader(
        "Drag and drop PDF files here (or click to browse)",
        type=['pdf'],
        accept_multiple_files=True,
        help="Supports RBC, TD, BMO, Scotiabank, CIBC, Tangerine, National Bank, AMEX • Upload multiple files at once",
        key=uploader_key
    )
    
    if uploaded_files:
        # Check if files have changed (clear results if so)
        current_file_names = [f.name for f in uploaded_files]
        if 'last_uploaded_files' not in st.session_state:
            st.session_state.last_uploaded_files = []
        
        # If files changed (different files or different order), clear results
        if current_file_names != st.session_state.last_uploaded_files:
            st.session_state.processed_files = []
            st.session_state.last_uploaded_files = current_file_names
        
        # Show file list
        st.success(f"{len(uploaded_files)} file(s) uploaded successfully")
        
        # Add clear files button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Clear All Files", type="secondary", use_container_width=True):
                # Clear all session state related to files
                st.session_state.processed_files = []
                st.session_state.last_uploaded_files = []
                st.session_state.file_order = []
                # Force clear the file uploader by changing its key
                st.session_state.uploader_key = f"uploader_{st.session_state.get('uploader_counter', 0) + 1}"
                st.session_state.uploader_counter = st.session_state.get('uploader_counter', 0) + 1
                st.rerun()
        
        # Determine processing mode
        is_batch_mode = len(uploaded_files) > 1
        
        if is_batch_mode:
            st.info("Multiple files detected - Will create combined output")
            
            # File reordering feature for batch mode
            st.subheader("Reorder Files (Optional)")
            st.caption("Use up/down buttons to reorder files - they will be processed in this order")
            
            # Initialize file order if not set
            if not st.session_state.file_order or len(st.session_state.file_order) != len(uploaded_files):
                st.session_state.file_order = list(range(len(uploaded_files)))
            
            # Display files with reorder controls
            for i, file_idx in enumerate(st.session_state.file_order):
                file = uploaded_files[file_idx]
                col1, col2, col3, col4 = st.columns([1, 6, 1, 1])
                
                with col1:
                    st.write("≡")  # Visual drag handle
                with col2:
                    st.write(f"**{file.name}** ({file.size / 1024:.1f} KB)")
                with col3:
                    if st.button("↑", key=f"up_{i}", disabled=(i == 0)):
                        # Move up
                        if i > 0:
                            st.session_state.file_order[i], st.session_state.file_order[i-1] = st.session_state.file_order[i-1], st.session_state.file_order[i]
                            st.rerun()
                with col4:
                    if st.button("↓", key=f"down_{i}", disabled=(i == len(st.session_state.file_order)-1)):
                        # Move down
                        if i < len(st.session_state.file_order)-1:
                            st.session_state.file_order[i], st.session_state.file_order[i+1] = st.session_state.file_order[i+1], st.session_state.file_order[i]
                            st.rerun()
            
            # Reorder uploaded_files based on session state
            reordered_files = [uploaded_files[i] for i in st.session_state.file_order]
            uploaded_files = reordered_files
        else:
            st.info("Single file - Will create individual output")
        
        # Process button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            process_btn = st.button(
                "Process Bank Statements",
                type="primary",
                use_container_width=True
            )
        
        if process_btn:
            process_files(uploaded_files, is_credit_card, is_batch_mode)
    
    # Clear results if no files are uploaded
    if not uploaded_files and st.session_state.processed_files:
        st.session_state.processed_files = []
        st.session_state.last_uploaded_files = []
    
    # Show results if available
    if st.session_state.processed_files:
        st.divider()
        show_results()
    elif not uploaded_files:
        # Show placeholder when no files are uploaded
        st.divider()
        st.info("Upload PDF bank or credit card statements above to get started")
        st.markdown("""
        **Supported:** RBC, TD, BMO, Scotiabank, CIBC, Tangerine, National Bank, AMEX (bank & credit card)  
        **Download:** Excel + QuickBooks IIF (same IIF script as `excel_to_iif.py` — works for both account types)
        """)
    
    # Excel → IIF: convert user-uploaded Excel to QuickBooks IIF
    st.divider()
    st.subheader("Excel → QuickBooks IIF")
    st.caption("Already have an Excel file with transactions? Convert it to IIF for QuickBooks import (bank or credit card).")
    excel_upload = st.file_uploader(
        "Upload Excel file (.xlsx)",
        type=["xlsx", "xls"],
        key="excel_iif_upload",
        help="Excel must have columns: Date, Description, and either Amount (credit card) or Withdrawals & Deposits (bank). Optionally: Account.",
    )
    if excel_upload:
        # Clear previous result when a new file is uploaded
        if st.session_state.get("excel_iif_last_name") != excel_upload.name:
            st.session_state.excel_iif_result = None
            st.session_state.excel_iif_filename = None
            st.session_state.excel_iif_last_name = excel_upload.name
        account_name = st.text_input(
            "QuickBooks account name (optional)",
            value="",
            key="iif_account_name",
            placeholder="e.g. TD 4738 or Scotia Visa — leave blank to auto-detect from filename",
        )
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            convert_btn = st.button("Convert to IIF", key="convert_excel_iif", type="primary")
        if convert_btn:
            with tempfile.TemporaryDirectory() as d:
                excel_path = Path(d) / excel_upload.name
                iif_path = Path(d) / (Path(excel_upload.name).stem + ".iif")
                excel_path.write_bytes(excel_upload.getvalue())
                out_buf, err_buf = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                    result = excel_to_iif(
                        str(excel_path),
                        str(iif_path),
                        bank_account_name=account_name.strip() or None,
                        skip_account_definitions=False,
                    )
                if result and iif_path.exists():
                    st.session_state.excel_iif_result = iif_path.read_text(encoding="utf-8")
                    st.session_state.excel_iif_filename = Path(excel_upload.name).stem + ".iif"
                    st.success("IIF file ready. Download below.")
                else:
                    st.error(
                        "Conversion failed. Ensure the Excel has a sheet with columns: **Date**, **Description**, "
                        "and either **Amount** (credit card) or **Withdrawals** & **Deposits** (bank). Optionally **Account**."
                    )
        if st.session_state.excel_iif_result:
            st.download_button(
                label="Download QuickBooks IIF",
                data=st.session_state.excel_iif_result,
                file_name=st.session_state.excel_iif_filename,
                mime="text/plain",
                key="dl_excel_iif",
                type="primary",
            )

def process_files(uploaded_files, is_credit_card, is_batch_mode):
    """Process uploaded PDF files
    
    Args:
        uploaded_files: List of uploaded PDF files
        is_credit_card: Credit card mode flag
        is_batch_mode: If True (multiple files), create combined output
    """
    
    # Initialize pipeline
    with st.spinner("Loading AI model..."):
        try:
            # Redirect stdout/stderr during load so Streamlit's closed streams don't cause "I/O operation on closed file"
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                pipeline = PDFToQuickBooks(quiet=True)
        except Exception as e:
            st.error(f"Error loading AI model: {e}")
            return
    
    st.success("✅ AI model loaded!")
    
    # Create temp directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Save uploaded files
        pdf_paths = []
        for uploaded_file in uploaded_files:
            file_path = temp_path / uploaded_file.name
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            pdf_paths.append(file_path)
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_results = []
        
        # Process each file
        for idx, pdf_path in enumerate(pdf_paths):
            progress = (idx + 1) / len(pdf_paths)
            progress_bar.progress(progress)
            status_text.text(f"Processing {pdf_path.name}... ({idx + 1}/{len(pdf_paths)})")
            
            try:
                # Extract with standardized bank extractors, then predict + save (same pipeline as process_to_excel)
                with st.spinner(f"Extracting and categorizing {pdf_path.name}..."):
                    result = extract_bank_statement(str(pdf_path))
                    if not result.success:
                        st.error(f"❌ {pdf_path.name}: Extraction failed - {result.error}")
                        continue
                    df_extracted = result.df.copy()
                    if df_extracted is None or len(df_extracted) == 0:
                        st.error(f"❌ {pdf_path.name}: No transactions found")
                        continue
                    # Ensure Running_Balance ties to opening balance (like process_to_excel)
                    opening = result.metadata.get('opening_balance')
                    if opening is not None and 'Running_Balance' not in df_extracted.columns:
                        if 'Withdrawals' in df_extracted.columns and 'Deposits' in df_extracted.columns:
                            w = pd.to_numeric(df_extracted['Withdrawals'], errors='coerce').fillna(0)
                            d = pd.to_numeric(df_extracted['Deposits'], errors='coerce').fillna(0)
                            df_extracted['Running_Balance'] = float(opening) + (d - w).cumsum()
                        elif 'Amount' in df_extracted.columns:
                            amt = pd.to_numeric(df_extracted['Amount'], errors='coerce').fillna(0)
                            df_extracted['Running_Balance'] = float(opening) + amt.cumsum()
                    pipeline._last_extracted_df = df_extracted
                    df_std, _ = pipeline._convert_to_standard_format(df_extracted, is_credit_card=None)
                    df = pipeline.predict_accounts(df_std)

                    if df is not None and len(df) > 0:
                        # Detect if this is a credit card from the dataframe structure
                        # Credit cards have 'Amount' column, bank accounts have 'Withdrawals'/'Deposits'
                        is_credit_card = 'Amount' in df.columns and 'Withdrawals' not in df.columns
                        
                        # Generate output files in memory
                        excel_buffer = io.BytesIO()
                        
                        # Use pipeline's save_to_excel (Option A: pass opening/closing so Excel has correct running balance + Summary)
                        pipeline.save_to_excel(
                            df, excel_buffer, is_credit_card=is_credit_card,
                            opening_balance=result.metadata.get('opening_balance'),
                            closing_balance=result.metadata.get('closing_balance')
                        )
                        excel_buffer.seek(0)
                        excel_data = excel_buffer.read()
                        
                        # Generate IIF via excel_to_iif script (bank & credit card)
                        iif_data = _generate_iif_from_dataframe(df)
                        if iif_data is None:
                            iif_data = ""
                        
                        # Add source file to dataframe for batch mode
                        df['Source_File'] = pdf_path.name
                        
                        # Store results with file data in memory (include balances for verification)
                        all_results.append({
                            'filename': pdf_path.name,
                            'transactions': len(df),
                            'dataframe': df,
                            'excel_data': excel_data,
                            'iif_data': iif_data,
                            'high_confidence': (df['Confidence'] > 0.8).sum(),
                            'medium_confidence': ((df['Confidence'] > 0.5) & (df['Confidence'] <= 0.8)).sum(),
                            'low_confidence': (df['Confidence'] <= 0.5).sum(),
                            'opening_balance': result.metadata.get('opening_balance'),
                            'closing_balance': result.metadata.get('closing_balance'),
                        })
                        
                        st.success(f"✅ {pdf_path.name}: {len(df)} transactions processed")
                    else:
                        st.error(f"❌ {pdf_path.name}: No transactions found")
            
            except Exception as e:
                st.error(f"❌ {pdf_path.name}: Error - {str(e)}")
        
        progress_bar.progress(1.0)
        status_text.text("✅ Processing complete!")
        
        # Store results in session state
        st.session_state.processed_files = all_results
        st.session_state.is_batch_mode = is_batch_mode
        
        # Summary
        if all_results:
            
            total_transactions = sum(r['transactions'] for r in all_results)
            total_high = sum(r['high_confidence'] for r in all_results)
            total_medium = sum(r['medium_confidence'] for r in all_results)
            total_low = sum(r['low_confidence'] for r in all_results)
            
            st.divider()
            st.header("Processing Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Files Processed", len(all_results))
            with col2:
                st.metric("Total Transactions", total_transactions)
            with col3:
                st.metric("High Confidence", f"{total_high} ({total_high/total_transactions*100:.1f}%)")
            with col4:
                st.metric("Review Needed", f"{total_low} ({total_low/total_transactions*100:.1f}%)")
            
            # # Download section
            # st.divider()
            # st.header("Download Results")
            
            if is_batch_mode:
                # BATCH MODE: Create combined files ONLY (no individual files)
                # st.write("**Combined Output** - All transactions from all files merged into 2 files")
                
                # Combine all dataframes
                combined_df = pd.concat([r['dataframe'] for r in all_results], ignore_index=True)
                
                # (Combined files created in show_results() function, not here)
                

def show_results():
    """Display processing results"""
    
    st.header("Results")
    
    if st.session_state.is_batch_mode:
        # BATCH MODE: Show combined results
        st.subheader("Combined Results - All Files")
        
        # Calculate combined totals
        total_transactions = sum(r['transactions'] for r in st.session_state.processed_files)
        total_high = sum(r['high_confidence'] for r in st.session_state.processed_files)
        total_medium = sum(r['medium_confidence'] for r in st.session_state.processed_files)
        total_low = sum(r['low_confidence'] for r in st.session_state.processed_files)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Transactions", total_transactions)
        with col2:
            st.metric("High Confidence", f"{total_high} ({total_high/total_transactions*100:.1f}%)")
        with col3:
            st.metric("Medium Confidence", f"{total_medium} ({total_medium/total_transactions*100:.1f}%)")
        with col4:
            st.metric("Low Confidence", f"{total_low} ({total_low/total_transactions*100:.1f}%)")
        
        # Combine all dataframes
        combined_df = pd.concat([r['dataframe'] for r in st.session_state.processed_files], ignore_index=True)
        
        # Balance verification (per file): opening/closing from PDF; running total from transactions; Match = last row equals statement closing
        if any(r.get('closing_balance') is not None for r in st.session_state.processed_files):
            st.subheader("Balance verification")
            st.caption("Opening and closing balances come from the PDF. **Running total** is computed from transactions. **Match ✓** means the last row’s running total equals the statement closing balance (within $0.02).")
            balance_rows = []
            for r in st.session_state.processed_files:
                df_f = r['dataframe']
                last_bal = float(df_f['Running_Balance'].iloc[-1]) if 'Running_Balance' in df_f.columns and len(df_f) else None
                closing = r.get('closing_balance')
                opening = r.get('opening_balance')
                if closing is not None and last_bal is not None:
                    match = abs(last_bal - float(closing)) < 0.02
                    balance_rows.append({
                        'File': r['filename'],
                        'Opening': f"${float(opening):,.2f}" if opening is not None else "—",
                        'Closing (statement)': f"${float(closing):,.2f}",
                        'Last row running total': f"${last_bal:,.2f}",
                        'Match': "✓ Yes" if match else "✗ No"
                    })
            if balance_rows:
                st.dataframe(pd.DataFrame(balance_rows), use_container_width=True, hide_index=True)
        
        # Display combined transactions
        st.subheader("All Transactions (Combined)")
        
        df_display = combined_df.copy()
        
        # Format for display
        if 'Date' in df_display.columns:
            df_display['Date'] = pd.to_datetime(df_display['Date']).dt.strftime('%Y-%m-%d')
        
        # Match process_to_excel Excel layout: Debit, Deposit, Running Total (same column names as downloaded Excel)
        if 'Running_Balance' in df_display.columns:
            df_display['Running Total'] = df_display['Running_Balance'].apply(lambda x: f"${float(x):,.2f}" if pd.notna(x) else "")
        # Bank: Debit / Deposit columns (credit card keeps single Amount in Excel; here we still split for display)
        if 'Amount' in df_display.columns:
            df_display['Debit'] = df_display['Amount'].apply(lambda x: f"${abs(x):,.2f}" if x < 0 else "")
            df_display['Deposit'] = df_display['Amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else "")
        
        # Format confidence as percentage
        df_display['Confidence'] = df_display['Confidence'].apply(lambda x: f"{x:.1%}")
        
        # Add confidence indicator
        def get_confidence_indicator(conf_str):
            conf = float(conf_str.strip('%')) / 100
            if conf > 0.8:
                return "🟢 High"
            elif conf > 0.5:
                return "🟡 Medium"
            else:
                return "🟠 Low"
        
        df_display['Confidence Level'] = df_display['Confidence'].apply(get_confidence_indicator)
        
        # Column order like process_to_excel: Date, Description, Account, Debit, Deposit, Running Total, Confidence
        display_cols = ['Confidence Level', 'Source_File', 'Date', 'Description', 'Account', 'Debit', 'Deposit', 'Running Total', 'Confidence']
        display_cols = [col for col in display_cols if col in df_display.columns]
        
        # Dataframe with colored confidence indicators
        st.dataframe(
            df_display[display_cols],
            use_container_width=True,
            height=400,
            hide_index=True,
            column_config={
                "Confidence Level": st.column_config.TextColumn(
                    "Confidence Level",
                    help="🟢 High (>80%) | 🟡 Medium (50-80%) | 🟠 Low (<50%)"
                )
            }
        )
        
        st.caption("High confidence (>80%)  |  Medium (50-80%)  |  Low confidence (<50%) - review recommended")
        
        # Combined account summary
        st.subheader("Account Category Breakdown (Combined)")
        account_summary = combined_df.groupby('Account').agg({
            'Amount': ['count', 'sum'],
            'Confidence': 'mean'
        }).round(2)
        account_summary.columns = ['Transaction Count', 'Total Amount ($)', 'Avg Confidence']
        account_summary = account_summary.sort_values('Transaction Count', ascending=False)
        
        # Format the summary
        account_summary['Avg Confidence'] = account_summary['Avg Confidence'].apply(lambda x: f"{x:.1%}")
        
        st.dataframe(account_summary, use_container_width=True)
        
        # Download combined files
        st.divider()
        st.subheader("Download Combined Files")
        
        # Create combined Excel
        combined_excel_buffer = io.BytesIO()
        pipeline = PDFToQuickBooks(quiet=True)
        combined_is_credit_card = 'Amount' in combined_df.columns and 'Withdrawals' not in combined_df.columns
        pipeline.save_to_excel(combined_df, combined_excel_buffer, is_credit_card=combined_is_credit_card)
        combined_excel_buffer.seek(0)
        combined_excel_data = combined_excel_buffer.read()
        
        # Create combined IIF via excel_to_iif script (bank & credit card)
        combined_iif_data = _generate_iif_from_dataframe(combined_df) or ""
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download Combined Excel",
                data=combined_excel_data,
                file_name="all_statements_combined.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
        with col2:
            st.download_button(
                label="Download Combined QuickBooks IIF",
                data=combined_iif_data,
                file_name="all_statements_combined.iif",
                mime="text/plain",
                use_container_width=True,
                type="primary"
            )
    
    else:
        # SINGLE FILE MODE: Show individual file results
        result = st.session_state.processed_files[0]  # Only one file in single mode
        
        st.subheader(f"Results for: {result['filename']}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Transactions", result['transactions'])
        with col2:
            st.metric("High Confidence", f"{result['high_confidence']} ({result['high_confidence']/result['transactions']*100:.1f}%)")
        with col3:
            st.metric("Medium Confidence", f"{result['medium_confidence']} ({result['medium_confidence']/result['transactions']*100:.1f}%)")
        with col4:
            st.metric("Low Confidence", f"{result['low_confidence']} ({result['low_confidence']/result['transactions']*100:.1f}%)")
        
        # Balance verification (single file): opening/closing from PDF; Match = last row running total equals statement closing
        opening = result.get('opening_balance')
        closing = result.get('closing_balance')
        df_res = result['dataframe']
        last_bal = float(df_res['Running_Balance'].iloc[-1]) if 'Running_Balance' in df_res.columns and len(df_res) else None
        if closing is not None or last_bal is not None:
            match = (last_bal is not None and closing is not None and abs(last_bal - float(closing)) < 0.02)
            parts = []
            if opening is not None:
                parts.append(f"Opening: ${float(opening):,.2f}")
            if closing is not None:
                parts.append(f"Closing (statement): ${float(closing):,.2f}")
            if last_bal is not None:
                parts.append(f"Last row running total: ${last_bal:,.2f}")
            if closing is not None and last_bal is not None:
                parts.append(f"Match: {'✓ Yes' if match else '✗ No'}")
            if parts:
                st.caption("**Balance:**  " + "  |  ".join(parts) + " — *Opening/closing from PDF; running total from transactions. Match ✓ = last row equals statement closing (within $0.02).*")
        
        # Display transactions
        st.subheader("Transaction Details")
        
        df_display = result['dataframe'].copy()
        
        # Format for display
        if 'Date' in df_display.columns:
            df_display['Date'] = pd.to_datetime(df_display['Date']).dt.strftime('%Y-%m-%d')
        
        # Match process_to_excel Excel layout: Debit, Deposit, Running Total
        if 'Running_Balance' in df_display.columns:
            df_display['Running Total'] = df_display['Running_Balance'].apply(lambda x: f"${float(x):,.2f}" if pd.notna(x) else "")
        if 'Amount' in df_display.columns:
            df_display['Debit'] = df_display['Amount'].apply(lambda x: f"${abs(x):,.2f}" if x < 0 else "")
            df_display['Deposit'] = df_display['Amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else "")
        
        # Format confidence as percentage
        df_display['Confidence'] = df_display['Confidence'].apply(lambda x: f"{x:.1%}")
        
        # Add confidence indicator
        def get_confidence_indicator(conf_str):
            conf = float(conf_str.strip('%')) / 100
            if conf > 0.8:
                return "🟢 High"
            elif conf > 0.5:
                return "🟡 Medium"
            else:
                return "🟠 Low"
        
        df_display['Confidence Level'] = df_display['Confidence'].apply(get_confidence_indicator)
        
        # Column order like process_to_excel: Date, Description, Account, Debit, Deposit, Running Total, Confidence
        display_cols = ['Confidence Level', 'Date', 'Description', 'Account', 'Debit', 'Deposit', 'Running Total', 'Confidence']
        display_cols = [col for col in display_cols if col in df_display.columns]
        
        # Dataframe with colored confidence indicators
        st.dataframe(
            df_display[display_cols],
            use_container_width=True,
            height=400,
            hide_index=True,
            column_config={
                "Confidence Level": st.column_config.TextColumn(
                    "Confidence Level",
                    help="🟢 High (>80%) | 🟡 Medium (50-80%) | 🟠 Low (<50%)"
                )
            }
        )
        
        st.caption("High confidence (>80%)  |  Medium (50-80%)  |  Low confidence (<50%) - review recommended")
        
        # Account summary
        st.subheader("Account Category Breakdown")
        df_original = result['dataframe'].copy()
        account_summary = df_original.groupby('Account').agg({
            'Amount': ['count', 'sum'],
            'Confidence': 'mean'
        }).round(2)
        account_summary.columns = ['Transaction Count', 'Total Amount ($)', 'Avg Confidence']
        account_summary = account_summary.sort_values('Transaction Count', ascending=False)
        
        # Format the summary
        account_summary['Avg Confidence'] = account_summary['Avg Confidence'].apply(lambda x: f"{x:.1%}")
        
        st.dataframe(account_summary, use_container_width=True)
        
        # Download individual file
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download Excel",
                data=result['excel_data'],
                file_name=f"categorized_{Path(result['filename']).stem}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
        with col2:
            st.download_button(
                label="Download QuickBooks IIF",
                data=result['iif_data'],
                file_name=f"quickbooks_{Path(result['filename']).stem}.iif",
                mime="text/plain",
                use_container_width=True,
                type="primary"
            )

if __name__ == "__main__":
    main()

