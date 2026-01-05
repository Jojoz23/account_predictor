#!/usr/bin/env python3
"""
Process all Tangerine Bank statements and output to Excel
Uses original extract_tangerine_bank.py extractor + AI account prediction
"""

import pandas as pd
from pathlib import Path
from extract_tangerine_bank import extract_tangerine_bank_statement
from datetime import datetime
from pdf_to_quickbooks import PDFToQuickBooks

def process_tangerine_folder(folder_path="data/Tangeriene bank", output_file=None):
    """
    Process all Tangerine PDFs in a folder and save to Excel
    
    Parameters:
    - folder_path: Path to folder containing Tangerine PDFs
    - output_file: Output Excel file path (default: tangerine_statements_combined.xlsx)
    """
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder not found: {folder_path}")
        return None
    
    pdf_files = sorted(folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ No PDF files found in {folder_path}")
        return None
    
    print("="*80)
    print("TANGERINE BANK STATEMENT PROCESSOR")
    print("="*80)
    print(f"\n📁 Processing folder: {folder_path}")
    print(f"📄 Found {len(pdf_files)} PDF file(s)\n")
    
    # Initialize AI pipeline for account prediction
    try:
        print("🧠 Loading AI model for account prediction...")
        pipeline = PDFToQuickBooks()
        print("✅ Model loaded successfully\n")
    except Exception as e:
        print(f"⚠️  Warning: Could not load AI model: {e}")
        print("   Continuing without account predictions...\n")
        pipeline = None
    
    all_transactions = []
    results_summary = []
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        print(f"[{idx}/{len(pdf_files)}] Processing: {pdf_path.name}")
        
        try:
            df, opening_balance, closing_balance, statement_year = extract_tangerine_bank_statement(str(pdf_path))
            
            if df is not None and not df.empty:
                df = df.copy()
                
                # Convert Date to datetime first (required for prediction)
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                    df = df[df['Date'].notna()].reset_index(drop=True)
                
                if len(df) == 0:
                    print(f"   ⚠️  No valid dates found, skipping...")
                    continue
                
                # Convert Withdrawals/Deposits to Amount for prediction (if needed)
                if 'Amount' not in df.columns:
                    if 'Withdrawals' in df.columns and 'Deposits' in df.columns:
                        # Convert to Amount column (negative for withdrawals, positive for deposits)
                        df['Withdrawals'] = pd.to_numeric(df['Withdrawals'], errors='coerce').fillna(0)
                        df['Deposits'] = pd.to_numeric(df['Deposits'], errors='coerce').fillna(0)
                        df['Amount'] = df['Deposits'] - df['Withdrawals']
                    elif 'Withdrawals' in df.columns:
                        df['Withdrawals'] = pd.to_numeric(df['Withdrawals'], errors='coerce').fillna(0)
                        df['Amount'] = -df['Withdrawals']
                        df['Deposits'] = 0
                    elif 'Deposits' in df.columns:
                        df['Deposits'] = pd.to_numeric(df['Deposits'], errors='coerce').fillna(0)
                        df['Amount'] = df['Deposits']
                        df['Withdrawals'] = 0
                
                # Predict accounts using AI
                if pipeline is not None:
                    try:
                        df = pipeline.predict_accounts(df)
                    except Exception as e:
                        print(f"      ⚠️  Account prediction failed: {e}")
                        df['Account'] = 'Uncategorized'
                        df['Confidence'] = 0.0
                else:
                    df['Account'] = 'Uncategorized'
                    df['Confidence'] = 0.0
                
                # Add metadata columns (same value for all rows)
                df['Source_File'] = pdf_path.name
                df['Opening_Balance'] = opening_balance if opening_balance is not None else ''
                df['Closing_Balance'] = closing_balance if closing_balance is not None else ''
                df['Statement_Year'] = statement_year if statement_year is not None else ''
                
                all_transactions.append(df)
                
                print(f"   ✅ Extracted {len(df)} transactions")
                print(f"      Opening: ${opening_balance:,.2f}" if opening_balance is not None else "      Opening: N/A")
                print(f"      Closing: ${closing_balance:,.2f}" if closing_balance is not None else "      Closing: N/A")
                
                results_summary.append({
                    'File': pdf_path.name,
                    'Status': 'Success',
                    'Transactions': len(df),
                    'Opening_Balance': opening_balance if opening_balance is not None else '',
                    'Closing_Balance': closing_balance if closing_balance is not None else '',
                })
            else:
                error_msg = "No transactions extracted"
                print(f"   ❌ Failed: {error_msg}")
                
                results_summary.append({
                    'File': pdf_path.name,
                    'Status': 'Failed',
                    'Transactions': 0,
                    'Opening_Balance': '',
                    'Closing_Balance': '',
                    'Error': error_msg
                })
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            results_summary.append({
                'File': pdf_path.name,
                'Status': 'Error',
                'Transactions': 0,
                'Opening_Balance': '',
                'Closing_Balance': '',
                'Error': str(e)
            })
    
    if not all_transactions:
        print("\n❌ No transactions extracted from any files")
        return None
    
    # Combine all DataFrames
    print(f"\n📊 Combining {len(all_transactions)} file(s)...")
    combined_df = pd.concat(all_transactions, ignore_index=True)
    
    # Sort by date
    if 'Date' in combined_df.columns:
        combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')
        combined_df = combined_df.sort_values('Date').reset_index(drop=True)
    
    # Select only the columns we want: Date, Description, Account, Withdrawals, Deposits, Running_Balance
    columns_to_keep = []
    for col in ['Date', 'Description', 'Account', 'Withdrawals', 'Deposits', 'Running_Balance']:
        if col in combined_df.columns:
            columns_to_keep.append(col)
    
    # Keep any additional columns that exist (like Source_File for reference)
    combined_df_output = combined_df[columns_to_keep].copy()
    
    # Determine output file name
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"tangerine_statements_combined_{timestamp}.xlsx"
    else:
        output_file = Path(output_file)
        if output_file.suffix != '.xlsx':
            output_file = output_file.with_suffix('.xlsx')
    
    # Create summary DataFrame
    summary_df = pd.DataFrame(results_summary)
    
    # Write to Excel with multiple sheets
    print(f"\n💾 Saving to Excel: {output_file}")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Main transactions sheet (only selected columns)
        combined_df_output.to_excel(writer, sheet_name='Transactions', index=False)
        
        # Summary sheet
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # By account (if Account column exists)
        if 'Account' in combined_df.columns:
            account_summary = combined_df.groupby('Account').agg({
                'Withdrawals': 'sum' if 'Withdrawals' in combined_df.columns else 'count',
                'Deposits': 'sum' if 'Deposits' in combined_df.columns else 'count'
            }).reset_index()
            account_summary.to_excel(writer, sheet_name='By Account', index=False)
    
    print(f"✅ Successfully saved to: {output_file}")
    print(f"\n📈 Summary:")
    print(f"   Total files processed: {len(pdf_files)}")
    print(f"   Successful: {len([r for r in results_summary if r['Status'] == 'Success'])}")
    print(f"   Failed: {len([r for r in results_summary if r['Status'] != 'Success'])}")
    print(f"   Total transactions: {len(combined_df)}")
    
    return output_file

if __name__ == "__main__":
    import sys
    
    folder_path = sys.argv[1] if len(sys.argv) > 1 else "data/Tangeriene bank"
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    process_tangerine_folder(folder_path, output_file)

