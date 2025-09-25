#!/usr/bin/env python3
"""
Account Predictor - Use your trained model to predict account categories
"""

import joblib
import pandas as pd
import numpy as np
import re
from datetime import datetime

class AccountPredictor:
    def __init__(self, model_path='models/account_predictor_model_improved.pkl'):
        """Load the trained model and preprocessing objects"""
        print(f"Loading model from {model_path}...")
        
        # Load the model package
        model_package = joblib.load(model_path)
        
        self.model = model_package['model']
        self.tfidf_vectorizer = model_package['tfidf_vectorizer']
        self.feature_columns = model_package['feature_columns']
        self.class_names = model_package['class_names']
        self.feature_importance = model_package['feature_importance']
        
        print(f"Model loaded successfully!")
        print(f"Classes: {len(self.class_names)}")
        print(f"Features: {len(self.feature_columns)}")
    
    def clean_text(self, text):
        """Clean transaction descriptions for better feature extraction"""
        if pd.isna(text):
            return ""
        
        # Convert to lowercase
        text = str(text).lower()
        
        # Remove special characters but keep spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def predict_single(self, date, description, amount):
        """
        Predict account category for a single transaction
        
        Parameters:
        - date: Transaction date (string or datetime)
        - description: Transaction description (string)
        - amount: Transaction amount (float)
        
        Returns:
        - predicted_account: Predicted account category
        - confidence: Prediction confidence score
        - probabilities: All class probabilities
        """
        
        # Create a single-row DataFrame
        new_transaction = pd.DataFrame({
            'Date': [pd.to_datetime(date)],
            'Description': [description],
            'Amount': [amount]
        })
        
        # Create features (same as training)
        new_transaction['Year'] = new_transaction['Date'].dt.year
        new_transaction['Month'] = new_transaction['Date'].dt.month
        new_transaction['Day'] = new_transaction['Date'].dt.day
        new_transaction['DayOfWeek'] = new_transaction['Date'].dt.dayofweek
        new_transaction['IsWeekend'] = (new_transaction['DayOfWeek'] >= 5).astype(int)
        new_transaction['Quarter'] = new_transaction['Date'].dt.quarter
        
        new_transaction['Amount_Abs'] = new_transaction['Amount'].abs()
        new_transaction['IsIncome'] = (new_transaction['Amount'] > 0).astype(int)
        new_transaction['Amount_Log'] = np.log1p(new_transaction['Amount_Abs'])
        
        new_transaction['Description_Length'] = new_transaction['Description'].str.len()
        new_transaction['Word_Count'] = new_transaction['Description'].str.split().str.len()
        new_transaction['Has_Numbers'] = new_transaction['Description'].str.contains(r'\d').astype(int)
        new_transaction['Has_Special_Chars'] = new_transaction['Description'].str.contains(r'[!@#$%^&*(),.?":{}|<>]').astype(int)
        
        # Clean description for TF-IDF
        new_transaction['Description_Clean'] = new_transaction['Description'].apply(self.clean_text)
        
        # Create TF-IDF features
        tfidf_features = self.tfidf_vectorizer.transform(new_transaction['Description_Clean'])
        tfidf_df_new = pd.DataFrame(
            tfidf_features.toarray(),
            columns=[f'tfidf_{word}' for word in self.tfidf_vectorizer.get_feature_names_out()]
        )
        
        # Combine features
        X_new = pd.concat([new_transaction[self.feature_columns], tfidf_df_new], axis=1)
        
        # Ensure same columns as training data (fill missing with 0)
        all_columns = self.feature_columns + [f'tfidf_{word}' for word in self.tfidf_vectorizer.get_feature_names_out()]
        X_new = X_new.reindex(columns=all_columns, fill_value=0)
        
        # Make prediction
        prediction = self.model.predict(X_new)[0]
        confidence = self.model.predict_proba(X_new).max()
        probabilities = self.model.predict_proba(X_new)[0]
        
        # Create probability dictionary
        prob_dict = dict(zip(self.class_names, probabilities))
        
        return prediction, confidence, prob_dict
    
    def predict_batch(self, transactions):
        """
        Predict account categories for multiple transactions
        
        Parameters:
        - transactions: List of tuples (date, description, amount)
        
        Returns:
        - List of predictions with confidence scores
        """
        results = []
        
        for date, description, amount in transactions:
            prediction, confidence, probabilities = self.predict_single(date, description, amount)
            results.append({
                'date': date,
                'description': description,
                'amount': amount,
                'predicted_account': prediction,
                'confidence': confidence,
                'top_3_probabilities': sorted(probabilities.items(), key=lambda x: x[1], reverse=True)[:3]
            })
        
        return results
    
    def get_feature_importance(self, top_n=20):
        """Get the most important features"""
        return self.feature_importance.head(top_n)
    
    def get_class_names(self):
        """Get all possible account categories"""
        return self.class_names.tolist()


def main():
    """Example usage"""
    # Initialize the predictor
    predictor = AccountPredictor()
    
    # Example 1: Single prediction
    print("\n" + "="*60)
    print("SINGLE PREDICTION EXAMPLE")
    print("="*60)
    
    date = "2024-01-15"
    description = "Office Supplies - Staples"
    amount = -45.50
    
    prediction, confidence, probabilities = predictor.predict_single(date, description, amount)
    
    print(f"Date: {date}")
    print(f"Description: {description}")
    print(f"Amount: ${amount}")
    print(f"Predicted Account: {prediction}")
    print(f"Confidence: {confidence:.1%}")
    print(f"Top 3 possibilities:")
    for account, prob in sorted(probabilities.items(), key=lambda x: x[1], reverse=True)[:3]:
        print(f"  - {account}: {prob:.1%}")
    
    # Example 2: Batch predictions
    print("\n" + "="*60)
    print("BATCH PREDICTION EXAMPLE")
    print("="*60)
    
    transactions = [
        ("2024-01-15", "Office Supplies - Staples", -45.50),
        ("2024-01-16", "Client Payment - ABC Corp", 2500.00),
        ("2024-01-17", "Electricity Bill - ConEd", -120.75),
        ("2024-01-18", "Software Subscription - Adobe", -29.99),
        ("2024-01-19", "Business Lunch - Restaurant", -85.00)
    ]
    
    results = predictor.predict_batch(transactions)
    
    for result in results:
        print(f"{result['description']} (${result['amount']}) → {result['predicted_account']} ({result['confidence']:.1%})")
    
    # Example 3: Feature importance
    print("\n" + "="*60)
    print("TOP 10 MOST IMPORTANT FEATURES")
    print("="*60)
    
    importance = predictor.get_feature_importance(10)
    for i, (_, row) in enumerate(importance.iterrows(), 1):
        print(f"{i:2d}. {row['feature']}: {row['importance']:.4f}")


if __name__ == "__main__":
    main()
