#!/usr/bin/env python3
"""
Batch Account Predictor
Predicts account categories for multiple transactions from an Excel/CSV file
"""

import pandas as pd
import numpy as np
import joblib
import re
import warnings
import wordninja
warnings.filterwarnings('ignore')

def clean_text(text):
    """Clean transaction descriptions"""
    if pd.isna(text):
        return ""
    words = wordninja.split(str(text))
    text = ' '.join(words)
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    text = ' '.join(text.split())
    return text

def create_features(df):
    """Create features for batch prediction"""
    print("Creating features for batch prediction...")
    
    # Date features
    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month
    # df['Day'] = df['Date'].dt.day
    df['DayOfWeek'] = df['Date'].dt.dayofweek
    df['IsWeekend'] = (df['DayOfWeek'] >= 5).astype(int)
    df['Quarter'] = df['Date'].dt.quarter
    
    # Amount features
    df['Amount_Abs'] = df['Amount'].abs()
    df['IsIncome'] = (df['Amount'] > 0).astype(int)
    df['Amount_Log'] = np.log1p(df['Amount_Abs'])
    
    # Description features
    # df['Description_Length'] = df['Description'].str.len()
    # df['Word_Count'] = df['Description'].str.split().str.len()
    # df['Has_Numbers'] = df['Description'].str.contains(r'\d').astype(int)
    # df['Has_Special_Chars'] = df['Description'].str.contains(r'[!@#$%^&*(),.?":{}|<>]').astype(int)
    
    df['Amount_Range'] = pd.cut(df['Amount_Abs'], 
                           bins=[0, 50, 200, 500, 1000, 5000, float('inf')], 
                           labels=['Very_Small', 'Small', 'Medium', 'Large', 'Very_Large', 'Huge'])

    df['IsHighValue'] = (df['Amount_Abs'] > 1000).astype(int)  # High-value transactions
    df['IsRoundAmount'] = (df['Amount_Abs'] % 100 == 0).astype(int)  # Round amounts (common in sales)
    df['IsClientPayment'] = df['Description'].str.contains(r'payment|client|customer|invoice|bill', case=False, na=False).astype(int)
    df['IsRefund'] = df['Description'].str.contains(r'refund|return|credit', case=False, na=False).astype(int)

    # Clean descriptions for TF-IDF
    df['Description_Clean'] = df['Description'].apply(clean_text)
    
    return df

def predict_batch(input_file, output_file=None):
    """
    Predict account categories for a batch of transactions
    
    Parameters:
    - input_file: Path to Excel or CSV file with bookkeeping format:
      Expected columns: Date, Description, Withdrawals, Deposits, Balance
      OR standard format: Date, Description, Amount
    - output_file: Optional path to save results (default: adds '_predicted' to input filename)
    """
    
    print("BATCH ACCOUNT PREDICTOR")
    print("="*50)
    
    # Load the trained model
    print("Loading trained neural network model...")
    try:
        model_package = joblib.load('models/neural_network_account_predictor.pkl')
        model = model_package['model']
        scaler = model_package['scaler']
        label_encoder = model_package['label_encoder']
        tfidf = model_package['tfidf_vectorizer']
        basic_features = model_package['feature_columns']
        class_names = model_package['class_names']
        feature_columns_full = model_package['feature_columns_full']
        print("Model loaded successfully!")
    except FileNotFoundError:
        print("❌ Model file not found! Please run the neural network training notebook first.")
        return
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return
    
    # Load input data
    print(f"\nLoading data from: {input_file}")
    try:
        if input_file.endswith('.xlsx') or input_file.endswith('.xls'):
            # Try different encodings for Excel files
            try:
                df = pd.read_excel(input_file)
                print("✅ Excel file loaded successfully!")
            except Exception as e:
                print(f"❌ Error loading Excel file: {e}")
                return
        elif input_file.endswith('.csv'):
            # Try different encodings for CSV files
            try:
                df = pd.read_csv(input_file, encoding='utf-8')
                print("✅ CSV file loaded successfully!")
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(input_file, encoding='latin-1')
                    print("✅ CSV file loaded with latin-1 encoding!")
                except Exception as e:
                    print(f"❌ Error loading CSV file: {e}")
                    return
        else:
            print("❌ Unsupported file format. Please use .xlsx, .xls, or .csv files.")
            return
            
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    print(f"📊 Loaded {len(df)} transactions")
    print(f"Columns: {list(df.columns)}")
    
    # Check for bookkeeping format (Withdrawals/Deposits) or standard format (Amount)
    if 'Withdrawals' in df.columns and 'Deposits' in df.columns:
        print("📋 Detected bookkeeping format (Withdrawals/Deposits)")
        # Convert bookkeeping format to standard format
        print("Converting bookkeeping format to standard format...")
        
        # Create Amount column: Deposits are positive, Withdrawals are negative
        df['Amount'] = df['Deposits'].fillna(0) - df['Withdrawals'].fillna(0)
        
        # Remove rows where both Withdrawals and Deposits are empty/zero
        df = df[df['Amount'] != 0]
        
        print(f"📊 After conversion: {len(df)} transactions with non-zero amounts")
        
        # Show amount distribution
        positive_count = (df['Amount'] > 0).sum()
        negative_count = (df['Amount'] < 0).sum()
        print(f"  Deposits (positive): {positive_count}")
        print(f"  Withdrawals (negative): {negative_count}")
        
    elif 'Amount' in df.columns:
        print("📋 Detected standard format (Amount)")
    else:
        print("❌ Unsupported format. Expected either:")
        print("  - Bookkeeping format: Date, Description, Withdrawals, Deposits, Balance")
        print("  - Standard format: Date, Description, Amount")
        return
    
    # Check required columns
    required_columns = ['Date', 'Description', 'Amount']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"❌ Missing required columns: {missing_columns}")
        return
    
    # Clean and prepare data
    print("\nCleaning and preparing data...")
    
    # Remove rows with missing critical data
    original_count = len(df)
    df = df.dropna(subset=['Date', 'Description', 'Amount'])
    if len(df) < original_count:
        print(f"⚠️ Removed {original_count - len(df)} rows with missing data")
    
    # Convert Date to datetime
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    date_na = df['Date'].isna()
    if date_na.any():
        print(f"⚠️ Removing {date_na.sum()} rows with invalid dates")
        df = df[~date_na]
    
    # Clean Amount column
    df['Amount'] = df['Amount'].astype(str).str.replace(',', '').str.replace(' ', '')
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
    amount_na = df['Amount'].isna()
    if amount_na.any():
        print(f"⚠️ Removing {amount_na.sum()} rows with invalid amounts")
        df = df[~amount_na]
    
    print(f"📊 Processing {len(df)} valid transactions")
    
    # Create features
    df = create_features(df)
    
    # Create TF-IDF features
    print("Creating TF-IDF features...")
    tfidf_matrix = tfidf.transform(df['Description_Clean'])
    tfidf_df = pd.DataFrame(
        tfidf_matrix.toarray(),
        columns=[f'tfidf_{word}' for word in tfidf.get_feature_names_out()],
        index=df.index
    )
    
    # Combine features
    X_basic = df[basic_features].copy()
    X_combined = pd.concat([X_basic, tfidf_df], axis=1)

    X_combined = X_combined.reindex(columns=feature_columns_full, fill_value=0)
    
    # Scale features
    print("Scaling features...")
    X_scaled = scaler.transform(X_combined)
    
    # Make predictions
    print("Making predictions...")
    predictions_proba = model.predict(X_scaled, verbose=0)
    predictions_idx = np.argmax(predictions_proba, axis=1)
    predictions = label_encoder.inverse_transform(predictions_idx)
    confidences = np.max(predictions_proba, axis=1)
    
    # Add predictions to dataframe
    df['Predicted_Account'] = predictions
    df['Confidence'] = confidences
    
    # Get top 3 predictions for each transaction
    top_3_predictions = []
    for i, proba in enumerate(predictions_proba):
        top_3_idx = np.argsort(proba)[-3:][::-1]
        top_3 = [(class_names[idx], proba[idx]) for idx in top_3_idx]
        top_3_predictions.append(top_3)
    
    df['Top_3_Predictions'] = top_3_predictions
    
    # Display results
    print("\n🎯 PREDICTION RESULTS:")
    print("="*50)
    
    # Show prediction distribution
    prediction_counts = df['Predicted_Account'].value_counts()
    print("Prediction Distribution:")
    for account, count in prediction_counts.head(10).items():
        percentage = (count / len(df)) * 100
        print(f"  {account}: {count} ({percentage:.1f}%)")
    
    # Show confidence statistics
    print(f"\nConfidence Statistics:")
    print(f"  Average Confidence: {df['Confidence'].mean():.3f}")
    print(f"  Min Confidence: {df['Confidence'].min():.3f}")
    print(f"  Max Confidence: {df['Confidence'].max():.3f}")
    
    # Show some sample predictions
    print(f"\nSample Predictions:")
    print("-" * 50)
    for i in range(min(5, len(df))):
        row = df.iloc[i]
        print(f"{i+1}. {row['Description']} (${row['Amount']})")
        print(f"   → {row['Predicted_Account']} ({row['Confidence']:.1%} confidence)")
        top_3 = row['Top_3_Predictions']
        print(f"   Top 3: {', '.join([f'{acc}: {prob:.1%}' for acc, prob in top_3])}")
        print()
    
    # Save results
    if output_file is None:
        if input_file.endswith('.xlsx'):
            output_file = input_file.replace('.xlsx', '_predicted.xlsx')
        elif input_file.endswith('.xls'):
            output_file = input_file.replace('.xls', '_predicted.xlsx')
        elif input_file.endswith('.csv'):
            output_file = input_file.replace('.csv', '_predicted.csv')
        else:
            output_file = input_file + '_predicted.xlsx'
    
    print(f"💾 Saving results to: {output_file}")
    
    # Prepare output dataframe
    # Include original bookkeeping columns if they exist
    base_columns = ['Date', 'Description', 'Amount', 'Predicted_Account', 'Confidence']
    
    # Add original bookkeeping columns if they exist
    if 'Withdrawals' in df.columns:
        base_columns = ['Date', 'Description', 'Withdrawals', 'Deposits', 'Amount', 'Predicted_Account', 'Confidence']
    if 'Balance' in df.columns:
        base_columns.append('Balance')
    
    output_df = df[base_columns].copy()
    
    # Add top 3 predictions as separate columns
    for i in range(3):
        output_df[f'Top_{i+1}_Account'] = [pred[i][0] for pred in df['Top_3_Predictions']]
        output_df[f'Top_{i+1}_Confidence'] = [pred[i][1] for pred in df['Top_3_Predictions']]
    
    # Save file
    try:
        if output_file.endswith('.xlsx'):
            output_df.to_excel(output_file, index=False)
        else:
            output_df.to_csv(output_file, index=False)
        print("✅ Results saved successfully!")
    except Exception as e:
        print(f"❌ Error saving results: {e}")
        return
    
    print(f"\n🎉 BATCH PREDICTION COMPLETE!")
    print(f"📊 Processed: {len(df)} transactions")
    print(f"💾 Results saved to: {output_file}")
    print(f"📈 Average confidence: {df['Confidence'].mean():.1%}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python batch_predict.py <input_file> [output_file]")
        print("Example: python batch_predict.py data/Bookkeeping 2025.xlsx")
        print("Example: python batch_predict.py data/transactions.csv data/results.xlsx")
        print("\nSupported formats:")
        print("  - Bookkeeping format: Date, Description, Withdrawals, Deposits, Balance")
        print("  - Standard format: Date, Description, Amount")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    predict_batch(input_file, output_file)