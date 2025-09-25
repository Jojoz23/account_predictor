"""
Data processing utilities for account prediction model.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import re
from typing import List, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')


class TransactionProcessor:
    """Process and clean transaction data for machine learning."""
    
    def __init__(self):
        self.account_mapping = {}
        self.feature_columns = []
        
    def load_data(self, file_path: str) -> pd.DataFrame:
        """Load transaction data from CSV or Excel file."""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                raise ValueError("Unsupported file format. Use CSV or Excel files.")
                
        # Convert date column
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            
        # Reorder columns to standard format: Date, Description, Amount, Account
        expected_columns = ['Date', 'Description', 'Amount', 'Account']
        if all(col in df.columns for col in expected_columns):
            df = df[expected_columns]
                
            return df
        except Exception as e:
            print(f"Error loading data: {e}")
            return pd.DataFrame()
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize transaction data."""
        df_clean = df.copy()
        
        # Remove duplicates
        df_clean = df_clean.drop_duplicates()
        
        # Clean description text
        if 'Description' in df_clean.columns:
            df_clean['Description'] = df_clean['Description'].str.strip()
            df_clean['Description'] = df_clean['Description'].str.replace(r'\s+', ' ', regex=True)
            
        # Handle missing values
        df_clean = df_clean.dropna(subset=['Description', 'Amount', 'Account'])
        
        # Remove zero amounts
        df_clean = df_clean[df_clean['Amount'] != 0]
        
        # Standardize account names
        if 'Account' in df_clean.columns:
            df_clean['Account'] = df_clean['Account'].str.strip()
            df_clean['Account'] = df_clean['Account'].str.title()
            
        return df_clean
    
    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract features from transaction data."""
        df_features = df.copy()
        
        # Date features
        if 'Date' in df_features.columns:
            df_features['Year'] = df_features['Date'].dt.year
            df_features['Month'] = df_features['Date'].dt.month
            df_features['Day'] = df_features['Date'].dt.day
            df_features['DayOfWeek'] = df_features['Date'].dt.dayofweek
            df_features['IsWeekend'] = df_features['DayOfWeek'].isin([5, 6]).astype(int)
            
        # Amount features
        if 'Amount' in df_features.columns:
            df_features['Amount_Abs'] = df_features['Amount'].abs()
            df_features['IsIncome'] = (df_features['Amount'] > 0).astype(int)
            df_features['Amount_Log'] = np.log1p(df_features['Amount_Abs'])
            
        # Description features
        if 'Description' in df_features.columns:
            df_features['Description_Length'] = df_features['Description'].str.len()
            df_features['Word_Count'] = df_features['Description'].str.split().str.len()
            df_features['Has_Numbers'] = df_features['Description'].str.contains(r'\d').astype(int)
            df_features['Has_Special_Chars'] = df_features['Description'].str.contains(r'[!@#$%^&*(),.?":{}|<>]').astype(int)
            
            # Common keywords
            keywords = {
                'office': ['office', 'supplies', 'staples', 'paper', 'pens'],
                'utilities': ['electric', 'gas', 'water', 'internet', 'phone', 'bill'],
                'software': ['software', 'subscription', 'adobe', 'microsoft', 'license'],
                'travel': ['travel', 'hotel', 'flight', 'uber', 'taxi', 'gas'],
                'meals': ['restaurant', 'lunch', 'dinner', 'food', 'coffee', 'meal'],
                'revenue': ['payment', 'invoice', 'client', 'customer', 'sale']
            }
            
            for category, words in keywords.items():
                pattern = '|'.join(words)
                df_features[f'Contains_{category.title()}'] = df_features['Description'].str.contains(
                    pattern, case=False, regex=True
                ).astype(int)
        
        return df_features
    
    def prepare_training_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare data for model training."""
        # Clean and extract features
        df_clean = self.clean_data(df)
        df_features = self.extract_features(df_clean)
        
        # Define feature columns (exclude target and original columns)
        exclude_cols = ['Date', 'Description', 'Amount', 'Account']
        self.feature_columns = [col for col in df_features.columns if col not in exclude_cols]
        
        X = df_features[self.feature_columns]
        y = df_features['Account']
        
        return X, y
    
    def get_data_summary(self, df: pd.DataFrame) -> Dict:
        """Get summary statistics of the dataset."""
        summary = {
            'total_transactions': len(df),
            'unique_accounts': df['Account'].nunique() if 'Account' in df.columns else 0,
            'date_range': {
                'start': df['Date'].min() if 'Date' in df.columns else None,
                'end': df['Date'].max() if 'Date' in df.columns else None
            },
            'amount_stats': df['Amount'].describe().to_dict() if 'Amount' in df.columns else {},
            'account_distribution': df['Account'].value_counts().to_dict() if 'Account' in df.columns else {}
        }
        return summary


def main():
    """Example usage of the TransactionProcessor."""
    processor = TransactionProcessor()
    
    # Load sample data
    sample_data = {
        'Date': pd.date_range('2024-01-01', periods=100, freq='D'),
        'Description': ['Sample transaction ' + str(i) for i in range(100)],
        'Amount': np.random.normal(0, 100, 100),
        'Account': np.random.choice(['Office', 'Utilities', 'Software', 'Revenue'], 100)
    }
    
    df = pd.DataFrame(sample_data)
    
    # Process data
    X, y = processor.prepare_training_data(df)
    
    print("Feature columns:", processor.feature_columns)
    print("X shape:", X.shape)
    print("y shape:", y.shape)
    print("Sample features:")
    print(X.head())


if __name__ == "__main__":
    main()

