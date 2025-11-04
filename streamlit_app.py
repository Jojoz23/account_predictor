"""
Bank Statement PDF to QuickBooks - Streamlit Web App

HOW THIS APP WORKS:
==================

1. USER UPLOADS PDFs
   - You drag & drop bank statement PDFs (RBC, TD, BMO, Scotiabank, CIBC)
   - Can upload single file or multiple files at once

2. EXTRACTION (extract_bank_statements.py)
   - Reads PDF using Camelot (table extraction) and pdfplumber (text extraction)
   - Detects which bank from the PDF content
   - Extracts all transactions: Date, Description, Amount
   - Handles multi-line descriptions, deduplication, date parsing

3. AI CATEGORIZATION (pdf_to_quickbooks.py)
   - Loads pre-trained neural network model (28 QuickBooks account categories)
   - For each transaction:
     * Analyzes the description using TF-IDF (text analysis)
     * Considers date, amount, transaction patterns
     * Predicts the best account category (e.g., "Office Expense", "Sales")
     * Provides confidence score (0-100%)
   
4. OUTPUT FILES
   - Excel file: Human-readable with categories, confidence scores
   - QuickBooks IIF file: Ready to import into QuickBooks Desktop

5. USER DOWNLOADS
   - Individual files: Download Excel + IIF for each statement
   - Batch ZIP: All files packaged together

KEY FEATURES:
- Stores files in memory (not on disk) for security
- Color-coded confidence indicators (🟢 🟡 🔴)
- Real-time progress tracking
- Works offline (runs locally)
"""

import streamlit as st
import pandas as pd
import os
import tempfile
from pathlib import Path
from pdf_to_quickbooks import PDFToQuickBooks
from extract_bank_statements import extract_from_pdf
import zipfile
import io

# Page configuration
st.set_page_config(
    page_title="Bookeepifier",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit branding (menu, footer, header)
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
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

def main():
    # Header
    st.title("Bookeepifier")
    st.markdown("Upload PDF bank statements (RBC, TD, BMO, Scotiabank, CIBC) → AI categorizes transactions → Download Excel & QuickBooks files")
    
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
        help="Supports RBC, TD, BMO, Scotiabank, CIBC • Upload multiple files at once",
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
        st.info("Upload PDF bank statements above to get started")
        st.markdown("""
        **Supported Banks:** RBC, TD, BMO, Scotiabank, CIBC  
        **Features:** AI-powered transaction categorization, Excel & QuickBooks export  
        **Drag & Drop:** You can drop files anywhere on this page
        """)

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
            pipeline = PDFToQuickBooks()
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
                # Process the PDF
                with st.spinner(f"Extracting and categorizing {pdf_path.name}..."):
                    df = pipeline.process_pdf(str(pdf_path), is_credit_card=False)  # Force bank mode for now
                    
                    if df is not None and len(df) > 0:
                        # Generate output files in memory using proper save methods
                        excel_buffer = io.BytesIO()
                        iif_buffer = io.StringIO()
                        
                        # Use pipeline's save_to_excel method (creates Debit/Deposit columns)
                        pipeline.save_to_excel(df, excel_buffer, is_credit_card=False)
                        excel_buffer.seek(0)
                        excel_data = excel_buffer.read()
                        
                        # Use pipeline's save_to_quickbooks_iif method
                        pipeline.save_to_quickbooks_iif(df, iif_buffer)
                        iif_data = iif_buffer.getvalue()
                        
                        # Add source file to dataframe for batch mode
                        df['Source_File'] = pdf_path.name
                        
                        # Store results with file data in memory
                        all_results.append({
                            'filename': pdf_path.name,
                            'transactions': len(df),
                            'dataframe': df,
                            'excel_data': excel_data,
                            'iif_data': iif_data,
                            'high_confidence': (df['Confidence'] > 0.8).sum(),
                            'medium_confidence': ((df['Confidence'] > 0.5) & (df['Confidence'] <= 0.8)).sum(),
                            'low_confidence': (df['Confidence'] <= 0.5).sum()
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
        
        # Display combined transactions
        st.subheader("All Transactions (Combined)")
        
        df_display = combined_df.copy()
        
        # Format for display
        if 'Date' in df_display.columns:
            df_display['Date'] = pd.to_datetime(df_display['Date']).dt.strftime('%Y-%m-%d')
        
        # Create Debit and Deposit columns
        df_display['Withdrawals'] = df_display['Amount'].apply(lambda x: f"${abs(x):,.2f}" if x < 0 else '')
        df_display['Deposits'] = df_display['Amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else '')
        
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
        
        # Select columns to display (include Source_File for batch mode)
        display_cols = ['Confidence Level', 'Source_File', 'Date', 'Description', 'Account', 'Withdrawals', 'Deposits', 'Confidence']
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
        pipeline = PDFToQuickBooks()
        pipeline.save_to_excel(combined_df, combined_excel_buffer, is_credit_card=False)
        combined_excel_buffer.seek(0)
        combined_excel_data = combined_excel_buffer.read()
        
        # Create combined IIF
        combined_iif_buffer = io.StringIO()
        pipeline.save_to_quickbooks_iif(combined_df, combined_iif_buffer)
        combined_iif_data = combined_iif_buffer.getvalue()
        
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
        
        # Display transactions
        st.subheader("Transaction Details")
        
        df_display = result['dataframe'].copy()
        
        # Format for display
        if 'Date' in df_display.columns:
            df_display['Date'] = pd.to_datetime(df_display['Date']).dt.strftime('%Y-%m-%d')
        
        # Create Debit and Deposit columns
        df_display['Withdrawals'] = df_display['Amount'].apply(lambda x: f"${abs(x):,.2f}" if x < 0 else '')
        df_display['Deposits'] = df_display['Amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else '')
        
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
        
        # Select columns to display (no Source_File for single mode)
        display_cols = ['Confidence Level', 'Date', 'Description', 'Account', 'Withdrawals', 'Deposits', 'Confidence']
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

