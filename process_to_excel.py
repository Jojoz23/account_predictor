#!/usr/bin/env python3
"""
Generic Bank Statement to Excel Processor
Processes any bank statement folder using standardized extractors
Works with both bank accounts and credit cards
"""

import sys
import io

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import pandas as pd
from pathlib import Path
from datetime import datetime
from standardized_bank_extractors import extract_bank_statement
from pdf_to_quickbooks import PDFToQuickBooks


def _collect_pdf_paths(paths):
    """
    Collect PDF file paths from a list of paths (folders and/or individual PDFs).
    Returns sorted list of Path objects.
    """
    pdf_files = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"⚠️  Path not found, skipping: {path}")
            continue
        if path.is_file():
            if path.suffix.lower() == '.pdf':
                pdf_files.append(path)
            else:
                print(f"⚠️  Not a PDF, skipping: {path}")
        else:
            pdf_files.extend(sorted(path.glob("*.pdf")))
    return sorted(set(pdf_files))


def process_folder_to_excel(folder_path, output_filename=None, pdf_paths=None):
    """
    Process PDFs and create a combined Excel file.
    Accepts either a folder path (all PDFs in folder) or an explicit list of PDF paths.
    Automatically detects bank type using standardized extractors.

    Parameters:
    - folder_path: Optional path to folder containing PDF files (used if pdf_paths is None)
    - output_filename: Optional output filename (default: auto-generated with timestamp)
    - pdf_paths: Optional list of paths (folders and/or individual PDFs). If given, folder_path is ignored for input (still used for output directory if output_filename is relative).

    Returns:
    - Path to the created Excel file, or None if failed
    """
    if pdf_paths is not None:
        pdf_files = _collect_pdf_paths(pdf_paths)
        # Output directory: first path's parent if it's a file, else first path
        first = Path(pdf_paths[0])
        out_dir = first.parent if first.is_file() else first
    else:
        folder = Path(folder_path)
        if not folder.exists():
            print(f"❌ Folder not found: {folder_path}")
            return None
        pdf_files = sorted(folder.glob("*.pdf"))
        out_dir = folder

    if not pdf_files:
        print(f"❌ No PDF files found.")
        return None

    print(f"="*80)
    print(f"PROCESSING BANK STATEMENTS: {len(pdf_files)} PDF(s)")
    print(f"="*80)
    print(f"\nFound {len(pdf_files)} PDF file(s)\n")
    
    # Initialize PDFToQuickBooks pipeline for account prediction
    print("Loading AI model for account prediction...")
    try:
        pipeline = PDFToQuickBooks()
    except Exception as e:
        print(f"⚠️  Could not load AI model: {e}")
        print("   Processing without account prediction...")
        pipeline = None
    
    all_transactions = []
    results_summary = []
    is_credit_card = None  # Will be determined from first successful extraction
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
        print("-" * 80)
        
        try:
            # Extract using standardized extractor
            result = extract_bank_statement(str(pdf_file))
            
            if not result.success:
                print(f"❌ Extraction failed: {result.error}")
                results_summary.append({
                    'File': pdf_file.name,
                    'Status': 'Failed',
                    'Transactions': 0,
                    'Opening_Balance': '',
                    'Closing_Balance': '',
                    'Error': result.error
                })
                continue
            
            df = result.df
            
            if df is None or len(df) == 0:
                print(f"⚠️  No transactions extracted")
                results_summary.append({
                    'File': pdf_file.name,
                    'Status': 'Failed',
                    'Transactions': 0,
                    'Opening_Balance': '',
                    'Closing_Balance': '',
                    'Error': 'No transactions extracted'
                })
                continue
            
            df = df.copy()
            
            # Per-file account type (batch is_credit_card used for output format; first file sets it)
            file_is_credit_card = result.metadata.get('is_credit_card', False)
            if is_credit_card is None:
                is_credit_card = file_is_credit_card
            print(f"   💳 Detected type: {'Credit Card' if file_is_credit_card else 'Bank Account'}")
            
            # Get opening/closing balance from metadata
            opening_balance = result.metadata.get('opening_balance')
            closing_balance = result.metadata.get('closing_balance')
            
            # Convert Date to datetime first (required for prediction)
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df[df['Date'].notna()].reset_index(drop=True)
            
            if len(df) == 0:
                print(f"   ⚠️  No valid dates found, skipping...")
                results_summary.append({
                    'File': pdf_file.name,
                    'Status': 'Failed',
                    'Transactions': 0,
                    'Opening_Balance': '',
                    'Closing_Balance': '',
                    'Error': 'No valid dates found'
                })
                continue
            
            print(f"✅ Extracted {len(df)} transactions")
            
            # Filter out "Opening balance", "Balance forward", and empty/NaN descriptions (for Excel output consistency)
            if 'Description' in df.columns:
                mask = (
                    ~df['Description'].astype(str).str.contains('Opening balance|Balance forward', case=False, na=False) &
                    df['Description'].notna() &
                    (df['Description'].astype(str).str.strip() != '') &
                    (df['Description'].astype(str).str.strip() != 'nan')
                )
                df = df[mask].reset_index(drop=True)
                print(f"   Filtered out opening/balance/empty rows: {len(df)} transactions remaining")
            
            # For CIBC: Calculate deposits from balance changes (if Balance column exists)
            # This matches the Jan 12 Excel output which correctly identifies deposits
            if result.metadata.get('bank') == 'CIBC' and 'Balance' in df.columns and 'Withdrawals' in df.columns and 'Deposits' in df.columns:
                # Calculate previous balance for each transaction
                df['Prev_Balance'] = df['Balance'].shift(1)
                # For first transaction after filtering, use opening balance
                if opening_balance is not None:
                    df.loc[df.index[0], 'Prev_Balance'] = opening_balance
                
                # Calculate balance change
                df['Balance_Change'] = df['Balance'] - df['Prev_Balance']
                
                # Update deposits and withdrawals based on balance changes
                for idx in df.index:
                    withdrawal = df.at[idx, 'Withdrawals']
                    balance_change = df.at[idx, 'Balance_Change']
                    
                    if pd.notna(withdrawal) and withdrawal != 0:
                        # If balance increased despite having a withdrawal amount, it's actually a deposit
                        if balance_change > 0:
                            df.at[idx, 'Deposits'] = withdrawal
                            df.at[idx, 'Withdrawals'] = 0
                    elif pd.isna(withdrawal) or withdrawal == 0:
                        # No withdrawal amount set, check if balance change indicates deposit
                        if balance_change > 0:
                            df.at[idx, 'Deposits'] = abs(balance_change)
                            df.at[idx, 'Withdrawals'] = 0
                        elif balance_change < 0:
                            df.at[idx, 'Withdrawals'] = abs(balance_change)
                            df.at[idx, 'Deposits'] = 0
                
                # Drop temporary columns
                df = df.drop(columns=['Prev_Balance', 'Balance_Change'], errors='ignore')
                
                # Recalculate Running_Balance using deposits/withdrawals
                if opening_balance is not None:
                    df['Net_Change'] = df['Deposits'].fillna(0) - df['Withdrawals'].fillna(0)
                    df['Running_Balance'] = opening_balance + df['Net_Change'].cumsum()
            
            # Handle Amount column based on this file's account type
            if file_is_credit_card:
                # Credit cards should already have Amount column
                if 'Amount' not in df.columns:
                    print(f"   ⚠️  Warning: Credit card missing Amount column")
                    df['Amount'] = 0
                # Convert Amount to numeric
                df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
                # INVERT amounts for AI model: Credit cards show +$100 = Charge (expense), -$50 = Payment (income)
                # Model expects: -$100 = Expense, +$50 = Income
                df['Amount'] = -df['Amount']
            else:
                # Bank accounts: convert Withdrawals/Deposits to Amount if needed
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
                    else:
                        print(f"   ⚠️  Warning: No amount columns found")
                        df['Amount'] = 0
                else:
                    # Ensure Amount is numeric
                    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
            
            # Predict accounts using AI
            if pipeline is not None:
                try:
                    print("🧠 Predicting account categories...")
                    df = pipeline.predict_accounts(df)
                    print(f"✅ Account prediction complete")
                    # Invert amounts back for credit cards (for Excel output)
                    if file_is_credit_card:
                        df['Amount'] = -df['Amount']
                except Exception as e:
                    print(f"      ⚠️  Account prediction failed: {e}")
                    df['Account'] = 'Uncategorized'
                    df['Confidence'] = 0.0
                    # Invert amounts back if prediction failed
                    if file_is_credit_card:
                        df['Amount'] = -df['Amount']
            else:
                df['Account'] = 'Uncategorized'
                df['Confidence'] = 0.0
            
            # Add source file
            df['Source_File'] = pdf_file.name
            
            # Add sequence number to preserve order within file
            df['_file_sequence'] = range(len(df))
            
            # Validate running balance matches closing balance
            balance_match = False
            final_rb = None
            balance_diff = None
            if 'Running_Balance' in df.columns and len(df) > 0:
                final_rb = df['Running_Balance'].iloc[-1]
                if closing_balance is not None:
                    balance_diff = abs(final_rb - closing_balance)
                    balance_match = balance_diff < 0.01
            
            all_transactions.append(df)
            
            print(f"   ✅ Processed {len(df)} transactions")
            print(f"      Opening: ${opening_balance:,.2f}" if opening_balance is not None else "      Opening: N/A")
            print(f"      Closing: ${closing_balance:,.2f}" if closing_balance is not None else "      Closing: N/A")
            if final_rb is not None:
                print(f"      Final Running Balance: ${final_rb:,.2f}")
                if closing_balance is not None:
                    if balance_match:
                        print(f"      ✅ Running balance matches closing balance!")
                    else:
                        print(f"      ⚠️  Balance difference: ${balance_diff:,.2f}")
            
            results_summary.append({
                'File': pdf_file.name,
                'Status': 'Success' if balance_match or closing_balance is None else 'Warning',
                'Transactions': len(df),
                'Opening_Balance': opening_balance if opening_balance is not None else '',
                'Closing_Balance': closing_balance if closing_balance is not None else '',
                'Final_Running_Balance': final_rb if final_rb is not None else '',
                'Balance_Match': 'Yes' if balance_match else ('N/A' if closing_balance is None else 'No'),
                'Balance_Diff': f"${balance_diff:,.2f}" if balance_diff is not None else ''
            })
            
        except Exception as e:
            print(f"❌ Error processing {pdf_file.name}: {e}")
            import traceback
            traceback.print_exc()
            results_summary.append({
                'File': pdf_file.name,
                'Status': 'Error',
                'Transactions': 0,
                'Opening_Balance': '',
                'Closing_Balance': '',
                'Error': str(e)
            })
            continue
    
    if not all_transactions:
        print("\n❌ No transactions extracted from any files")
        return None
    
    # Combine all transactions
    combined_df = pd.concat(all_transactions, ignore_index=True)
    
    # Sort by date, but preserve original order within same date using file sequence
    if 'Date' in combined_df.columns:
        combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')
        # Sort by date first, then by source file name, then by sequence within file
        combined_df = combined_df.sort_values(['Date', 'Source_File', '_file_sequence']).reset_index(drop=True)
        # Remove the temporary sequence column
        combined_df = combined_df.drop(columns=['_file_sequence'])
    
    # Select columns based on account type
    if is_credit_card:
        # Credit card format: Date, Description, Account, Amount, Running_Balance
        columns_to_keep = []
        for col in ['Date', 'Description', 'Account', 'Amount', 'Running_Balance']:
            if col in combined_df.columns:
                columns_to_keep.append(col)
    else:
        # Bank account format: Date, Description, Account, Withdrawals, Deposits, Running_Balance
        columns_to_keep = []
        for col in ['Date', 'Description', 'Account', 'Withdrawals', 'Deposits', 'Running_Balance']:
            if col in combined_df.columns:
                columns_to_keep.append(col)
    
    combined_df_output = combined_df[columns_to_keep].copy()
    
    # Format dates to date-only (remove time component) for Excel
    if 'Date' in combined_df_output.columns:
        combined_df_output['Date'] = pd.to_datetime(combined_df_output['Date']).dt.date
    
    # Generate output filename
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = out_dir.name.replace(" ", "_").replace("-", "_") if pdf_files else "statements"
        output_filename = f"{base_name}_combined_{timestamp}.xlsx"
    
    output_path = Path(output_filename)
    if not output_path.is_absolute():
        output_path = out_dir / output_filename
    
    # Create summary DataFrame
    summary_df = pd.DataFrame(results_summary)
    
    # Save to Excel with multiple sheets
    print(f"\n{'='*80}")
    print(f"SAVING COMBINED RESULTS")
    print(f"{'='*80}")
    print(f"\nTotal transactions: {len(combined_df)}")
    print(f"Files processed: {len(all_transactions)}")
    print(f"Account type: {'Credit Card' if is_credit_card else 'Bank Account'}")
    print(f"\nSaving to: {output_path}")
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Main transactions sheet
        combined_df_output.to_excel(writer, sheet_name='Transactions', index=False)
        
        # Summary sheet
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # By account (if Account column exists)
        if 'Account' in combined_df.columns:
            if is_credit_card:
                account_summary = combined_df.groupby('Account').agg({
                    'Amount': 'sum'
                }).reset_index()
            else:
                account_summary = combined_df.groupby('Account').agg({
                    'Withdrawals': 'sum' if 'Withdrawals' in combined_df.columns else 'count',
                    'Deposits': 'sum' if 'Deposits' in combined_df.columns else 'count'
                }).reset_index()
            account_summary.to_excel(writer, sheet_name='By Account', index=False)
    
    print(f"✅ Combined Excel file saved: {output_path}")
    print(f"\n📈 Summary:")
    success_count = len([r for r in results_summary if r['Status'] == 'Success'])
    warning_count = len([r for r in results_summary if r['Status'] == 'Warning'])
    fail_count = len([r for r in results_summary if r['Status'] in ('Failed', 'Error')])
    print(f"   Total files processed: {len(pdf_files)}")
    print(f"   Successful: {success_count}")
    if warning_count:
        print(f"   Warnings (balance mismatch): {warning_count}")
    if fail_count:
        print(f"   Failed: {fail_count}")
    print(f"   Total transactions: {len(combined_df)}")
    
    return output_path


def main():
    """Main function - accepts folder path(s) and/or individual PDF path(s)"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Process bank statement PDFs to combined Excel file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python process_to_excel.py "data/Scotia- Personal credit card"
  python process_to_excel.py "data/Account Statements CAD - CIBC 4213"
  python process_to_excel.py "data/pdfs/statement.pdf"
  python process_to_excel.py "data/pdfs/file1.pdf" "data/pdfs/file2.pdf"
  python process_to_excel.py "data/NB- Company Credit Card 1074" --output "nb_cc_combined.xlsx"
        """
    )
    
    parser.add_argument(
        'paths',
        nargs='*',
        help='Folder path(s) and/or individual PDF file path(s)'
    )
    parser.add_argument(
        '--output', '-o',
        dest='output_filename',
        help='Output filename (default: auto-generated with timestamp)'
    )
    
    args = parser.parse_args()
    
    if not args.paths:
        parser.print_help()
        print("\n" + "="*80)
        print("Please provide at least one folder path or PDF file path")
        print("="*80)
        return
    
    print("="*80)
    print("BANK STATEMENTS - COMBINED EXCEL GENERATOR")
    print("="*80)
    print("\nThis script processes bank statements using standardized extractors")
    print("and creates a combined Excel file with account predictions.\n")
    
    # Single folder: keep legacy behavior (one path that is a directory)
    if len(args.paths) == 1:
        p = Path(args.paths[0])
        if p.exists() and p.is_dir():
            output_path = process_folder_to_excel(args.paths[0], args.output_filename)
        else:
            output_path = process_folder_to_excel(None, args.output_filename, pdf_paths=args.paths)
    else:
        output_path = process_folder_to_excel(None, args.output_filename, pdf_paths=args.paths)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if output_path:
        print(f"\n✅ Successfully created combined Excel file:")
        print(f"   {output_path}")
    else:
        print("\n❌ Processing failed or no files were processed")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
