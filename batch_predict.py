#!/usr/bin/env python3
"""
Batch Account Predictor - Process CSV files with transactions
"""

import pandas as pd
import sys
from predict_account import AccountPredictor

def process_csv(input_file, output_file=None):
    """
    Process a CSV file with transactions and add predictions
    
    Expected CSV format: Date,Description,Amount
    """
    
    # Load the predictor
    predictor = AccountPredictor()
    
    # Read input CSV
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)
    
    # Check required columns
    required_columns = ['Date', 'Description', 'Amount']
    if not all(col in df.columns for col in required_columns):
        print(f"Error: CSV must have columns: {required_columns}")
        print(f"Found columns: {list(df.columns)}")
        return
    
    print(f"Processing {len(df)} transactions...")
    
    # Make predictions
    predictions = []
    confidences = []
    
    for idx, row in df.iterrows():
        if idx % 100 == 0:
            print(f"Processing transaction {idx + 1}/{len(df)}...")
        
        try:
            prediction, confidence, _ = predictor.predict_single(
                row['Date'], 
                row['Description'], 
                row['Amount']
            )
            predictions.append(prediction)
            confidences.append(confidence)
        except Exception as e:
            print(f"Error processing row {idx + 1}: {e}")
            predictions.append("ERROR")
            confidences.append(0.0)
    
    # Add predictions to dataframe
    df['Predicted_Account'] = predictions
    df['Confidence'] = confidences
    
    # Save results
    if output_file is None:
        output_file = input_file.replace('.csv', '_with_predictions.csv')
    
    df.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")
    
    # Show summary
    print(f"\nSummary:")
    print(f"Total transactions: {len(df)}")
    print(f"Average confidence: {df['Confidence'].mean():.1%}")
    print(f"High confidence (>80%): {(df['Confidence'] > 0.8).sum()}")
    print(f"Low confidence (<50%): {(df['Confidence'] < 0.5).sum()}")
    
    print(f"\nTop predicted accounts:")
    print(df['Predicted_Account'].value_counts().head(10))

def main():
    if len(sys.argv) < 2:
        print("Usage: python batch_predict.py <input_csv> [output_csv]")
        print("Example: python batch_predict.py transactions.csv predictions.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    process_csv(input_file, output_file)

if __name__ == "__main__":
    main()
