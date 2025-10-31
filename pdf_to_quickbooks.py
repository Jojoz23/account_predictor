#!/usr/bin/env python3
"""
End-to-End Pipeline: Bank Statement PDF → Extract → Predict Accounts → Export to QuickBooks
Processes PDF bank statements and categorizes transactions using AI
"""

import pandas as pd
import numpy as np
import joblib
import warnings
import os
import re
import wordninja
from pathlib import Path
from datetime import datetime
from extract_bank_statements import extract_from_pdf, extract_from_folder

warnings.filterwarnings('ignore')


class PDFToQuickBooks:
    """
    Complete pipeline: Extract PDF → Predict Accounts → Export for QuickBooks
    """
    
    def __init__(self, model_path='models/neural_network_account_predictor.pkl'):
        """
        Initialize the pipeline with trained model
        
        Parameters:
        - model_path: Path to the trained neural network model
        """
        print("🚀 BANK STATEMENT PDF TO QUICKBOOKS PIPELINE")
        print("="*70)
        print("\n📦 Loading AI model...")
        
        try:
            model_package = joblib.load(model_path)
            self.model = model_package['model']
            self.scaler = model_package['scaler']
            self.label_encoder = model_package['label_encoder']
            self.tfidf = model_package['tfidf_vectorizer']
            self.basic_features = model_package['feature_columns']
            self.class_names = model_package['class_names']
            self.feature_columns_full = model_package['feature_columns_full']
            print(f"✅ Model loaded successfully!")
            print(f"   Trained on {len(self.class_names)} account categories")
        except FileNotFoundError:
            print("❌ Model file not found!")
            print("   Please run the neural network training notebook first:")
            print("   notebooks/03_neural_network_training.ipynb")
            raise
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            raise
    
    def clean_text(self, text):
        """Clean transaction descriptions (same as training)"""
        if pd.isna(text):
            return ""
        words = wordninja.split(str(text))
        text = ' '.join(words)
        text = text.lower()
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        text = ' '.join(text.split())
        return text
    
    def build_basic_features(self, df):
        """
        Build basic features from transactions (same as training)
        """
        # Date features
        df['Year'] = df['Date'].dt.year
        df['Month'] = df['Date'].dt.month
        df['DayOfWeek'] = df['Date'].dt.dayofweek
        df['IsWeekend'] = (df['DayOfWeek'] >= 5).astype(int)
        df['Quarter'] = df['Date'].dt.quarter
        
        # Amount features
        df['Amount_Abs'] = df['Amount'].abs()
        df['IsIncome'] = (df['Amount'] > 0).astype(int)
        df['Amount_Log'] = np.log1p(df['Amount_Abs'])
        
        # Enhanced features
        df['IsHighValue'] = (df['Amount_Abs'] > 1000).astype(int)
        df['IsClientPayment'] = df['Description'].str.contains(
            r'payment|client|customer|invoice|bill', case=False, na=False
        ).astype(int)
        df['IsRefund'] = df['Description'].str.contains(
            r'refund|return|credit', case=False, na=False
        ).astype(int)
        
        # Clean description
        df['Description_Clean'] = df['Description'].apply(self.clean_text)
        
        return df
    
    def predict_accounts(self, df):
        """
        Predict account categories for all transactions
        
        Parameters:
        - df: DataFrame with Date, Description, Amount columns
        
        Returns:
        - DataFrame with predicted Account column and confidence scores
        """
        print(f"\n🧠 Predicting account categories for {len(df)} transactions...")
        
        # Build features
        df = self.build_basic_features(df)
        
        # Extract basic features
        basic_feature_cols = [
            'Year', 'Month', 'DayOfWeek', 'IsWeekend', 'Quarter',
            'Amount_Abs', 'IsIncome', 'Amount_Log',
            'IsHighValue', 'IsClientPayment', 'IsRefund'
        ]
        X_basic = df[basic_feature_cols].copy()
        
        # TF-IDF features
        tfidf_matrix = self.tfidf.transform(df['Description_Clean'])
        tfidf_cols = [f'tfidf_{word}' for word in self.tfidf.get_feature_names_out()]
        X_tfidf = pd.DataFrame(
            tfidf_matrix.toarray(),
            columns=tfidf_cols,
            index=X_basic.index
        )
        
        # Combine features
        X_combined = pd.concat([
            X_basic.reset_index(drop=True),
            X_tfidf.reset_index(drop=True)
        ], axis=1)
        
        # Align columns to match training
        X_combined = X_combined.reindex(columns=self.feature_columns_full, fill_value=0)
        
        # Scale features
        X_scaled = self.scaler.transform(X_combined)
        
        # Predict
        predictions = self.model.predict(X_scaled, verbose=0)
        predicted_indices = np.argmax(predictions, axis=1)
        predicted_accounts = self.label_encoder.inverse_transform(predicted_indices)
        confidence_scores = np.max(predictions, axis=1)
        
        # Add predictions to dataframe
        df['Account'] = predicted_accounts
        df['Confidence'] = confidence_scores
        
        # Get top 3 predictions for each transaction
        top3_accounts = []
        top3_confidences = []
        
        for pred in predictions:
            top3_idx = np.argsort(pred)[-3:][::-1]
            top3_acc = [self.label_encoder.inverse_transform([idx])[0] for idx in top3_idx]
            top3_conf = [pred[idx] for idx in top3_idx]
            top3_accounts.append(top3_acc)
            top3_confidences.append(top3_conf)
        
        df['Top_3_Accounts'] = [', '.join(acc) for acc in top3_accounts]
        df['Top_3_Confidence'] = [', '.join([f'{c:.2f}' for c in conf]) for conf in top3_confidences]
        
        # Summary
        print(f"✅ Predictions complete!")
        print(f"\n📊 Confidence Summary:")
        print(f"   High confidence (>80%): {(confidence_scores > 0.8).sum()} transactions")
        print(f"   Medium confidence (50-80%): {((confidence_scores > 0.5) & (confidence_scores <= 0.8)).sum()} transactions")
        print(f"   Low confidence (<50%): {(confidence_scores <= 0.5).sum()} transactions")
        
        print(f"\n📈 Top Predicted Accounts:")
        account_counts = df['Account'].value_counts().head(10)
        for account, count in account_counts.items():
            print(f"   {account}: {count} transactions")
        
        return df
    
    def process_pdf(self, pdf_path, output_excel=None, output_quickbooks=None, is_credit_card=None):
        """
        Complete pipeline: Extract PDF → Predict → Export
        
        Parameters:
        - pdf_path: Path to PDF bank statement
        - output_excel: Path for Excel output (default: auto-generated)
        - output_quickbooks: Path for QuickBooks IIF file (default: auto-generated)
        - is_credit_card: True/False/None (None = auto-detect)
        
        Returns:
        - DataFrame with predictions
        """
        print(f"\n📄 Processing: {os.path.basename(pdf_path)}")
        print("="*70)
        
        # Step 1: Extract transactions from PDF
        print("\n📋 STEP 1: Extracting transactions from PDF...")
        df_extracted = extract_from_pdf(pdf_path, save_excel=False)
        # Keep original extracted DF for later RB merge if needed
        self._last_extracted_df = df_extracted.copy() if df_extracted is not None else None
        
        if df_extracted is None or len(df_extracted) == 0:
            print("❌ Failed to extract transactions from PDF")
            return None
        
        # Preserve Running_Balance computed during extraction (if available)
        extracted_with_keys = df_extracted.copy()
        extracted_with_keys['Withdrawals'] = pd.to_numeric(extracted_with_keys.get('Withdrawals'), errors='coerce').fillna(0)
        extracted_with_keys['Deposits'] = pd.to_numeric(extracted_with_keys.get('Deposits'), errors='coerce').fillna(0)
        # Build a robust matching key using original columns
        def _mk_key(df):
            return (
                df['Date'].astype(str).str.strip() + '|' +
                df['Description'].astype(str).str.strip() + '|' +
                df['Withdrawals'].round(2).astype(str) + '|' +
                df['Deposits'].round(2).astype(str)
            )
        extracted_with_keys['_match_key'] = _mk_key(extracted_with_keys)
        extracted_running = extracted_with_keys[['_match_key', 'Running_Balance']] if 'Running_Balance' in extracted_with_keys.columns else None

        # Convert to standard format (Date, Description, Amount)
        df, was_credit_card = self._convert_to_standard_format(df_extracted, is_credit_card=is_credit_card)

        # Recreate the same key on the converted frame to merge Running_Balance
        df['_w'] = df['Amount'].apply(lambda x: -x if x < 0 else 0)
        df['_d'] = df['Amount'].apply(lambda x: x if x > 0 else 0)
        df['_match_key'] = (
            df['Date'].astype(str).str.strip() + '|' +
            df['Description'].astype(str).str.strip() + '|' +
            df['_w'].round(2).astype(str) + '|' +
            df['_d'].round(2).astype(str)
        )
        if extracted_running is not None:
            df = df.merge(extracted_running, on='_match_key', how='left')
        df = df.drop(columns=['_w', '_d', '_match_key'], errors='ignore')
        
        # Step 2: Predict account categories
        print("\n🧠 STEP 2: Predicting account categories...")
        df = self.predict_accounts(df)
        
        # Step 3: Export results (only if output paths provided)
        if output_excel or output_quickbooks:
            print("\n💾 STEP 3: Exporting results...")
            
            # Generate output filenames if not fully specified
            pdf_name = Path(pdf_path).stem
            
            if output_excel:
                # Save to Excel (with original credit card format if applicable)
                self.save_to_excel(df, output_excel, is_credit_card=was_credit_card)
            
            if output_quickbooks:
                # Save to QuickBooks format
                self.save_to_quickbooks_iif(df, output_quickbooks)
            
            print("\n" + "="*70)
            print("✅ PIPELINE COMPLETE!")
            print(f"📊 Processed {len(df)} transactions")
            if output_excel:
                print(f"💾 Excel file: {output_excel}")
            if output_quickbooks:
                print(f"💾 QuickBooks file: {output_quickbooks}")
            print("="*70)
        
        return df
    
    def process_folder(self, folder_path, output_folder=None, is_credit_card=None):
        """
        Process all PDFs in a folder
        
        Parameters:
        - folder_path: Path to folder with PDF bank statements
        - output_folder: Path for output files (default: same as input)
        - is_credit_card: True/False/None (None = auto-detect per file)
        
        Returns:
        - Combined DataFrame with all predictions
        """
        folder = Path(folder_path)
        # Preserve folder visual order by natural-sorting on the numeric prefix if present
        names = [f for f in os.listdir(folder) if f.lower().endswith('.pdf')]
        def numeric_prefix(name):
            # Handles prefixes like "-2. Febuary 2023.pdf", "10. January 2024.pdf", "7. October 2023.pdf"
            m = re.match(r'^\s*([+-]?\d+)\.', name)
            return int(m.group(1)) if m else None
        with_prefix = [(numeric_prefix(n), n) for n in names]
        if any(p is not None for p,_ in with_prefix):
            with_prefix.sort(key=lambda x: (float('inf') if x[0] is None else x[0]))
            ordered = [n for _, n in with_prefix]
        else:
            # Fallback to unsorted listing order
            ordered = names
        pdf_files = [folder / n for n in ordered]
        
        if not pdf_files:
            print(f"❌ No PDF files found in {folder_path}")
            return None
        
        print(f"\n📁 Processing {len(pdf_files)} PDF files...")
        print("="*70)
        
        all_results = []
        
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] {pdf_file.name}")
            try:
                # Extract and predict, but don't save individual files
                print(f"🔍 Extracting transactions from: {pdf_file.name}")
                print("="*70)
                
                # Step 1: Extract transactions from PDF
                from extract_bank_statements import extract_from_pdf
                df_extracted = extract_from_pdf(str(pdf_file), save_excel=False)
                
                if df_extracted is None or len(df_extracted) == 0:
                    print("❌ Failed to extract transactions")
                    continue
                
                # Step 2: Convert to standard format
                df_converted, was_credit_card = self._convert_to_standard_format(df_extracted, is_credit_card=is_credit_card)
                
                # Step 3: Predict account categories
                print("\n🧠 Predicting account categories...")
                df_predicted = self.predict_accounts(df_converted)
                
                # Add source file tracking
                df_predicted['Source_File'] = pdf_file.name
                all_results.append(df_predicted)
                
                print(f"✅ Processed {len(df_predicted)} transactions from {pdf_file.name}\n")
                
            except Exception as e:
                print(f"❌ Error processing {pdf_file.name}: {e}")
                continue
        
        if not all_results:
            print("\n❌ No transactions extracted from any files")
            return None
        
        # Combine all results
        combined_df = pd.concat(all_results, ignore_index=True)
        
        # Save combined results
        if output_folder is None:
            output_folder = folder
        else:
            output_folder = Path(output_folder)
            output_folder.mkdir(exist_ok=True)
        
        combined_excel = output_folder / "all_transactions_categorized.xlsx"
        combined_qb = output_folder / "all_transactions_quickbooks.iif"
        
        # For combined file, use bank format (separate Debit/Deposit) since mixing is complex
        self.save_to_excel(combined_df, combined_excel, is_credit_card=False)
        self.save_to_quickbooks_iif(combined_df, combined_qb)
        
        print("\n" + "="*70)
        print("✅ BATCH PROCESSING COMPLETE!")
        print(f"📊 Total transactions: {len(combined_df)}")
        print(f"📁 From {len(all_results)} files")
        print(f"💾 Combined Excel: {combined_excel}")
        print(f"💾 Combined QuickBooks: {combined_qb}")
        print("="*70)
        
        return combined_df
    
    def _detect_credit_card(self, df):
        """
        Auto-detect if this is a credit card statement
        
        Returns:
        - True if credit card detected
        - False if bank account detected
        """
        # Check descriptions for credit card indicators
        desc_text = ' '.join(df['Description'].astype(str).str.lower())
        
        # Credit card keywords
        cc_keywords = [
            'payment - thank you',
            'payment thank you',
            'payment received',
            'previous balance',
            'new balance',
            'credit card',
            'visa',
            'mastercard',
            'amex',
            'american express',
            'minimum payment',
            'interest charge',
            'annual fee',
            'cash advance'
        ]
        
        cc_keyword_count = sum(1 for keyword in cc_keywords if keyword in desc_text)
        
        # Bank account keywords
        bank_keywords = [
            'direct deposit',
            'eft credit',
            'eft debit',
            'wire transfer',
            'cheque',
            'check',
            'atm withdrawal',
            'pre-authorized'
        ]
        
        bank_keyword_count = sum(1 for keyword in bank_keywords if keyword in desc_text)
        
        # Decision logic
        if cc_keyword_count >= 2:
            return True
        
        if bank_keyword_count >= 2:
            return False
        
        # Check if positive amounts are mostly purchases (credit card indicator)
        if 'Amount' in df.columns:
            positive_desc = df[df['Amount'] > 0]['Description'].str.lower()
            if len(positive_desc) > 0:
                purchase_keywords = ['purchase', 'pos', 'sale', 'retail', 'restaurant', 'store']
                purchase_count = sum(1 for desc in positive_desc for keyword in purchase_keywords if keyword in str(desc))
                
                # If >30% of positive amounts are purchases, likely credit card
                if purchase_count / len(positive_desc) > 0.3:
                    return True
        
        # Default to bank account (safer - won't invert if uncertain)
        return False
    
    def _convert_to_standard_format(self, df, is_credit_card=None):
        """
        Convert bookkeeping format (Withdrawals/Deposits) to standard format (Amount)
        
        Parameters:
        - df: DataFrame with extracted transactions
        - is_credit_card: True (force credit card), False (force bank), None (auto-detect)
        
        Returns:
        - df: DataFrame with standardized Amount column
        - was_credit_card: Boolean indicating if this was a credit card (for display purposes)
        """
        # Clean Date column
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df[df['Date'].notna()]
        
        was_credit_card = False
        
        # CASE 1: Separate Withdrawals and Deposits columns (bank statements)
        if 'Withdrawals' in df.columns and 'Deposits' in df.columns:
            # Convert to numeric
            df['Withdrawals'] = pd.to_numeric(df['Withdrawals'], errors='coerce').fillna(0)
            df['Deposits'] = pd.to_numeric(df['Deposits'], errors='coerce').fillna(0)
            
            # Create Amount: Deposits are positive, Withdrawals are negative
            df['Amount'] = df['Deposits'] - df['Withdrawals']
            
            # Remove rows with zero amounts
            df = df[df['Amount'] != 0]
            
            print("  📊 Format: Withdrawals/Deposits columns → Standard Amount")
        
        # CASE 2: Single Amount column (could be credit card or bank)
        elif 'Amount' in df.columns:
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
            df = df[df['Amount'].notna()]
            
            # Auto-detect credit card if not specified
            if is_credit_card is None:
                is_credit_card = self._detect_credit_card(df)
                detection_method = "auto-detected"
            else:
                detection_method = "user-specified"
            
            # CREDIT CARD LOGIC:
            # Credit cards show: Positive = Charges (you owe), Negative = Payments (you paid)
            # We need: Negative = Expenses (money out), Positive = Income (money in)
            # Solution: INVERT the signs for AI processing!
            if is_credit_card:
                df['Amount'] = -df['Amount']
                was_credit_card = True
                print(f"  💳 Credit card {detection_method} - inverted amount signs for AI")
                print(f"     Charges (positive in PDF) → Expenses (negative for AI)")
                print(f"     Payments (negative in PDF) → Income (positive for AI)")
                print(f"     Note: Excel output will show original credit card format")
            else:
                print(f"  🏦 Bank account {detection_method} - amounts unchanged")
        
        else:
            raise ValueError("DataFrame must have either 'Amount' or 'Withdrawals'/'Deposits' columns")
        
        # Keep only essential columns
        essential_cols = ['Date', 'Description', 'Amount']
        if 'Balance' in df.columns:
            essential_cols.append('Balance')
        # Preserve the exact Running_Balance computed during extraction if present
        if 'Running_Balance' in df.columns:
            essential_cols.append('Running_Balance')
        
        df = df[essential_cols].copy()
        
        return df, was_credit_card
    
    def save_to_excel(self, df, output_path, is_credit_card=False):
        """
        Save to Excel with formatted sheets
        
        Parameters:
        - df: DataFrame with predictions
        - output_path: Path to save Excel file
        - is_credit_card: If True, invert amounts back to credit card format for display
        """
        # If Running_Balance is missing, attempt to merge from last extracted frame
        if 'Running_Balance' not in df.columns and hasattr(self, '_last_extracted_df') and isinstance(self._last_extracted_df, pd.DataFrame):
            src = self._last_extracted_df.copy()
            if not src.empty:
                src['Withdrawals'] = pd.to_numeric(src.get('Withdrawals'), errors='coerce').fillna(0)
                src['Deposits'] = pd.to_numeric(src.get('Deposits'), errors='coerce').fillna(0)
                src['_match_key'] = (
                    src['Date'].astype(str).str.strip() + '|' +
                    src['Description'].astype(str).str.strip() + '|' +
                    src['Withdrawals'].round(2).astype(str) + '|' +
                    src['Deposits'].round(2).astype(str)
                )
                temp = df.copy()
                temp['_w'] = temp['Amount'].apply(lambda x: -x if x < 0 else 0)
                temp['_d'] = temp['Amount'].apply(lambda x: x if x > 0 else 0)
                temp['_match_key'] = (
                    temp['Date'].astype(str).str.strip() + '|' +
                    temp['Description'].astype(str).str.strip() + '|' +
                    temp['_w'].round(2).astype(str) + '|' +
                    temp['_d'].round(2).astype(str)
                )
                rb_map = src[['_match_key','Running_Balance']] if 'Running_Balance' in src.columns else None
                if rb_map is not None:
                    temp = temp.merge(rb_map, on='_match_key', how='left')
                    df['Running_Balance'] = temp['Running_Balance']
                df.drop(columns=[c for c in ['_w','_d','_match_key'] if c in df.columns], inplace=True, errors='ignore')

        # Harmonize Date with extractor's Date (to preserve correct statement year)
        if hasattr(self, '_last_extracted_df') and isinstance(self._last_extracted_df, pd.DataFrame):
            srcD = self._last_extracted_df.copy()
            if not srcD.empty:
                srcD['Withdrawals'] = pd.to_numeric(srcD.get('Withdrawals'), errors='coerce').fillna(0)
                srcD['Deposits'] = pd.to_numeric(srcD.get('Deposits'), errors='coerce').fillna(0)
                srcD['_match_key'] = (
                    srcD['Date'].astype(str).str.strip() + '|' +
                    srcD['Description'].astype(str).str.strip() + '|' +
                    srcD['Withdrawals'].round(2).astype(str) + '|' +
                    srcD['Deposits'].round(2).astype(str)
                )
                tempD = df.copy()
                tempD['_w'] = tempD['Amount'].apply(lambda x: -x if x < 0 else 0)
                tempD['_d'] = tempD['Amount'].apply(lambda x: x if x > 0 else 0)
                tempD['_match_key'] = (
                    tempD['Date'].astype(str).str.strip() + '|' +
                    tempD['Description'].astype(str).str.strip() + '|' +
                    tempD['_w'].round(2).astype(str) + '|' +
                    tempD['_d'].round(2).astype(str)
                )
                date_map = srcD[['_match_key','Date']]
                tempD = tempD.merge(date_map, on='_match_key', how='left', suffixes=('', '_src'))
                # If a source Date is available, use it
                if 'Date_src' in tempD.columns:
                    try:
                        df['Date'] = pd.to_datetime(tempD['Date_src'], errors='coerce')
                    except Exception:
                        pass
                df.drop(columns=[c for c in ['_w','_d','_match_key'] if c in df.columns], inplace=True, errors='ignore')

        # Prepare display DataFrame
        # Compute Amount as shown in Excel (respect credit-card inversion)
        amt_display = -df['Amount'] if is_credit_card else df['Amount']
        # Running total should follow the same sign convention as displayed Amount
        # If multiple source files are combined, keep separate running totals per source file
        if 'Source_File' in df.columns:
            running_total = amt_display.groupby(df['Source_File']).cumsum()
        else:
            running_total = amt_display.cumsum()
        if is_credit_card:
            # Credit cards: Keep single Amount column with inverted signs
            display_df = df[[
                'Date', 'Description', 'Amount', 'Account', 'Confidence'
            ]].copy()
            
            # Invert amounts back to original format for Excel display
            display_df['Amount'] = -display_df['Amount']
            display_df['Running Total'] = running_total  # already in display sign convention
            print(f"  💳 Inverting amounts back to credit card format for Excel")
            print(f"     Charges will show as positive, payments as negative")
            
            # Format columns
            display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
            display_df['Amount'] = display_df['Amount'].apply(lambda x: f"${x:,.2f}")
            display_df['Running Total'] = display_df['Running Total'].apply(lambda x: f"${x:,.2f}")
            display_df['Confidence'] = display_df['Confidence'].apply(lambda x: f"{x:.1%}")
            # Reorder columns: place Running Total left of Confidence
            display_df = display_df[['Date', 'Description', 'Amount', 'Running Total', 'Account', 'Confidence']]
        else:
            # Bank statements: Split into Debit and Deposit columns
            display_df = df[['Date', 'Description', 'Account', 'Confidence']].copy()
            
            # Create Debit and Deposit columns (use None for empty cells, not empty string)
            display_df['Debit'] = df['Amount'].apply(lambda x: f"${abs(x):,.2f}" if x < 0 else None)
            display_df['Deposit'] = df['Amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else None)
            # Prefer Running_Balance from extractor when available; fallback to computed running_total
            if 'Running_Balance' in df.columns:
                running_balance_display = df['Running_Balance']
            else:
                running_balance_display = running_total
            # Use the "Running Total" label consistently
            display_df['Running Total'] = running_balance_display.apply(lambda x: f"${x:,.2f}")
            
            # Reorder columns: Date, Description, Account, Debit, Deposit, Running Total, Confidence
            display_df = display_df[['Date', 'Description', 'Account', 'Debit', 'Deposit', 'Running Total', 'Confidence']]
            
            # Format columns
            display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
            display_df['Confidence'] = display_df['Confidence'].apply(lambda x: f"{x:.1%}")
            
            print(f"  🏦 Bank statement format: Separate Debit and Deposit columns")
        
        # Save to Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Main sheet
            display_df.to_excel(writer, sheet_name='Categorized Transactions', index=False)
            
            # Summary sheet - use original df amounts (not display_df which has formatted strings)
            # For credit cards, we need to invert back for accurate summary
            summary_amounts = df['Amount'].copy()
            if is_credit_card:
                summary_amounts = -summary_amounts
            
            summary_data = {
                'Total Transactions': [len(df)],
                'Total Deposits': [f"${summary_amounts[summary_amounts > 0].sum():,.2f}"] if is_credit_card else [f"${df[df['Amount'] > 0]['Amount'].sum():,.2f}"],
                'Total Withdrawals': [f"${abs(summary_amounts[summary_amounts < 0].sum()):,.2f}"] if is_credit_card else [f"${abs(df[df['Amount'] < 0]['Amount'].sum()):,.2f}"],
                'Net Amount': [f"${summary_amounts.sum():,.2f}"] if is_credit_card else [f"${df['Amount'].sum():,.2f}"],
                'High Confidence (>80%)': [f"{(df['Confidence'] > 0.8).sum()} ({(df['Confidence'] > 0.8).sum() / len(df):.1%})"],
                'Medium Confidence (50-80%)': [f"{((df['Confidence'] > 0.5) & (df['Confidence'] <= 0.8)).sum()}"],
                'Low Confidence (<50%)': [f"{(df['Confidence'] <= 0.5).sum()}"],
            }
            
            # Add note for credit card statements
            if is_credit_card:
                summary_data['Statement Type'] = ['Credit Card (amounts shown in original format)']
            
            summary_df = pd.DataFrame(summary_data).T
            summary_df.columns = ['Value']
            summary_df.to_excel(writer, sheet_name='Summary')
            
            # Account breakdown
            account_df = df.copy()
            if is_credit_card:
                account_df['Amount'] = -account_df['Amount']
            
            account_summary = account_df.groupby('Account').agg({
                'Amount': ['count', 'sum'],
                'Confidence': 'mean'
            }).round(2)
            account_summary.columns = ['Count', 'Total Amount', 'Avg Confidence']
            account_summary = account_summary.sort_values('Count', ascending=False)
            account_summary.to_excel(writer, sheet_name='By Account')
        
        if not hasattr(output_path, 'write'):
            print(f"✅ Excel saved: {output_path}")
    
    def save_to_quickbooks_iif(self, df, output_path):
        """
        Save to QuickBooks IIF format for import
        """
        # QuickBooks IIF format for bank transactions
        iif_content = []
        
        # Header
        iif_content.append("!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tMEMO")
        iif_content.append("!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tMEMO")
        iif_content.append("!ENDTRNS")
        
        # Transactions
        for idx, row in df.iterrows():
            date_str = row['Date'].strftime('%m/%d/%Y')
            amount = row['Amount']
            description = str(row['Description'])[:100]  # Limit length
            account = row['Account']
            
            # Bank account (source)
            bank_account = "Checking Account"  # Default - can be customized
            
            # Transaction
            iif_content.append(f"TRNS\t{idx}\tDEPOSIT\t{date_str}\t{bank_account}\t\t\t{amount}\t\t{description}")
            iif_content.append(f"SPL\t{idx}\tDEPOSIT\t{date_str}\t{account}\t\t\t{-amount}\t\t{description}")
            iif_content.append("ENDTRNS")
        
        # Save to file or StringIO
        if hasattr(output_path, 'write'):
            # StringIO object
            output_path.write('\n'.join(iif_content))
        else:
            # File path
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(iif_content))
            print(f"✅ QuickBooks IIF saved: {output_path}")
            print(f"   Import this file into QuickBooks Desktop")


def main():
    """Command-line interface"""
    import sys
    
    if len(sys.argv) < 2:
        print("="*70)
        print("BANK STATEMENT PDF TO QUICKBOOKS PIPELINE")
        print("="*70)
        print("\nUsage:")
        print("  python pdf_to_quickbooks.py <pdf_file> [--credit-card | --bank]")
        print("  python pdf_to_quickbooks.py <folder_path> [--credit-card | --bank]")
        print("\nExamples:")
        print("  python pdf_to_quickbooks.py statements/RBC_Jan2024.pdf")
        print("  python pdf_to_quickbooks.py statements/Visa_Jan2024.pdf --credit-card")
        print("  python pdf_to_quickbooks.py statements/ --bank")
        print("\nFlags:")
        print("  --credit-card  Force credit card format (inverts amount signs)")
        print("  --bank         Force bank account format (no sign inversion)")
        print("  (no flag)      Auto-detect based on content")
        print("\nWhat this does:")
        print("  1. Extracts transactions from PDF bank statements")
        print("  2. Uses AI to predict account categories")
        print("  3. Exports to Excel and QuickBooks format")
        print("\nSupports: RBC, TD, BMO, Scotiabank, CIBC, and other Canadian banks")
        print("="*70)
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    # Check for credit card flag
    is_credit_card = None
    if '--credit-card' in sys.argv:
        is_credit_card = True
        print("🔧 Credit card mode: ENABLED (will invert amount signs)")
    elif '--bank' in sys.argv:
        is_credit_card = False
        print("🔧 Bank account mode: ENABLED (amounts unchanged)")
    else:
        print("🔧 Auto-detection mode: Will detect credit card vs bank account")
    
    # Initialize pipeline
    pipeline = PDFToQuickBooks()
    
    # Process input
    if os.path.isfile(input_path):
        # Single PDF file - auto-save outputs next to the input PDF
        pdf_path = Path(input_path)
        base = pdf_path.with_suffix('')
        out_excel = str(base) + "_categorized.xlsx"
        out_iif = str(base) + "_quickbooks.iif"
        pipeline.process_pdf(input_path, output_excel=out_excel, output_quickbooks=out_iif, is_credit_card=is_credit_card)
    elif os.path.isdir(input_path):
        # Folder of PDFs - use process_folder to create combined file
        pipeline.process_folder(input_path, is_credit_card=is_credit_card)
    else:
        print(f"❌ Path not found: {input_path}")


if __name__ == '__main__':
    main()

