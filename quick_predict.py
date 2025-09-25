#!/usr/bin/env python3
"""
Quick Account Predictor - Simple command-line interface
"""

import sys
from predict_account import AccountPredictor

def main():
    if len(sys.argv) != 4:
        print("Usage: python quick_predict.py <date> <description> <amount>")
        print("Example: python quick_predict.py '2024-01-15' 'Office Supplies - Staples' -45.50")
        sys.exit(1)
    
    date = sys.argv[1]
    description = sys.argv[2]
    amount = float(sys.argv[3])
    
    # Load model and predict
    predictor = AccountPredictor()
    prediction, confidence, probabilities = predictor.predict_single(date, description, amount)
    
    # Display results
    print(f"\nTransaction: {description}")
    print(f"Date: {date}")
    print(f"Amount: ${amount}")
    print(f"\nPredicted Account: {prediction}")
    print(f"Confidence: {confidence:.1%}")
    
    print(f"\nTop 3 possibilities:")
    for account, prob in sorted(probabilities.items(), key=lambda x: x[1], reverse=True)[:3]:
        print(f"  - {account}: {prob:.1%}")

if __name__ == "__main__":
    main()
