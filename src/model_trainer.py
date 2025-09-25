"""
Machine learning model training for account prediction.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
import xgboost as xgb
import lightgbm as lgb
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Tuple, List
import warnings
warnings.filterwarnings('ignore')


class AccountPredictor:
    """Train and evaluate models for account prediction."""
    
    def __init__(self):
        self.models = {}
        self.label_encoder = LabelEncoder()
        self.scaler = StandardScaler()
        self.feature_importance = {}
        self.best_model = None
        self.best_score = 0
        
    def prepare_data(self, X: pd.DataFrame, y: pd.Series, test_size: float = 0.2) -> Tuple:
        """Prepare data for training and testing."""
        # Encode target variable
        y_encoded = self.label_encoder.fit_transform(y)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=test_size, random_state=42, stratify=y_encoded
        )
        
        # Scale features for models that need it
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        return X_train, X_test, X_train_scaled, X_test_scaled, y_train, y_test
    
    def train_models(self, X_train, X_train_scaled, y_train) -> Dict:
        """Train multiple models and compare performance."""
        
        # Define models
        models = {
            'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'Gradient Boosting': GradientBoostingClassifier(random_state=42),
            'XGBoost': xgb.XGBClassifier(random_state=42, eval_metric='mlogloss'),
            'LightGBM': lgb.LGBMClassifier(random_state=42, verbose=-1),
            'Logistic Regression': LogisticRegression(random_state=42, max_iter=1000),
            'SVM': SVC(random_state=42, probability=True)
        }
        
        # Train models
        for name, model in models.items():
            print(f"Training {name}...")
            
            # Use scaled data for models that need it
            if name in ['Logistic Regression', 'SVM']:
                model.fit(X_train_scaled, y_train)
            else:
                model.fit(X_train, y_train)
            
            self.models[name] = model
            
        return self.models
    
    def evaluate_models(self, X_test, X_test_scaled, y_test) -> Dict:
        """Evaluate all trained models."""
        results = {}
        
        for name, model in self.models.items():
            # Use scaled data for models that need it
            if name in ['Logistic Regression', 'SVM']:
                y_pred = model.predict(X_test_scaled)
                y_pred_proba = model.predict_proba(X_test_scaled)
            else:
                y_pred = model.predict(X_test)
                y_pred_proba = model.predict_proba(X_test)
            
            # Calculate metrics
            accuracy = accuracy_score(y_test, y_pred)
            results[name] = {
                'accuracy': accuracy,
                'predictions': y_pred,
                'probabilities': y_pred_proba
            }
            
            print(f"{name} Accuracy: {accuracy:.4f}")
            
            # Store best model
            if accuracy > self.best_score:
                self.best_score = accuracy
                self.best_model = model
                
        return results
    
    def hyperparameter_tuning(self, X_train, X_train_scaled, y_train) -> Dict:
        """Perform hyperparameter tuning for the best model."""
        print("Performing hyperparameter tuning...")
        
        # Tune Random Forest (usually performs well for this type of problem)
        rf_params = {
            'n_estimators': [100, 200, 300],
            'max_depth': [10, 20, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }
        
        rf_grid = GridSearchCV(
            RandomForestClassifier(random_state=42),
            rf_params,
            cv=5,
            scoring='accuracy',
            n_jobs=-1
        )
        
        rf_grid.fit(X_train, y_train)
        
        print(f"Best Random Forest parameters: {rf_grid.best_params_}")
        print(f"Best Random Forest score: {rf_grid.best_score_:.4f}")
        
        # Update best model
        self.best_model = rf_grid.best_estimator_
        self.best_score = rf_grid.best_score_
        
        return rf_grid.best_params_
    
    def get_feature_importance(self, X_train) -> pd.DataFrame:
        """Get feature importance from the best model."""
        if hasattr(self.best_model, 'feature_importances_'):
            importance_df = pd.DataFrame({
                'feature': X_train.columns,
                'importance': self.best_model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            self.feature_importance = importance_df
            return importance_df
        else:
            print("Model doesn't support feature importance")
            return pd.DataFrame()
    
    def plot_feature_importance(self, top_n: int = 15):
        """Plot feature importance."""
        if self.feature_importance.empty:
            print("No feature importance data available")
            return
            
        plt.figure(figsize=(10, 8))
        top_features = self.feature_importance.head(top_n)
        
        sns.barplot(data=top_features, x='importance', y='feature')
        plt.title(f'Top {top_n} Feature Importance')
        plt.xlabel('Importance')
        plt.tight_layout()
        plt.show()
    
    def plot_confusion_matrix(self, y_test, y_pred):
        """Plot confusion matrix."""
        cm = confusion_matrix(y_test, y_pred)
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
        plt.title('Confusion Matrix')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.show()
    
    def save_model(self, filepath: str):
        """Save the trained model and preprocessing objects."""
        model_data = {
            'model': self.best_model,
            'label_encoder': self.label_encoder,
            'scaler': self.scaler,
            'feature_columns': list(self.feature_importance['feature']) if not self.feature_importance.empty else []
        }
        
        joblib.dump(model_data, filepath)
        print(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model."""
        model_data = joblib.load(filepath)
        
        self.best_model = model_data['model']
        self.label_encoder = model_data['label_encoder']
        self.scaler = model_data['scaler']
        
        print(f"Model loaded from {filepath}")
    
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions on new data."""
        if self.best_model is None:
            raise ValueError("No model loaded. Train or load a model first.")
        
        # Use scaled data if model needs it
        if hasattr(self.best_model, 'predict_proba'):
            if type(self.best_model).__name__ in ['LogisticRegression', 'SVC']:
                X_scaled = self.scaler.transform(X)
                predictions = self.best_model.predict(X_scaled)
                probabilities = self.best_model.predict_proba(X_scaled)
            else:
                predictions = self.best_model.predict(X)
                probabilities = self.best_model.predict_proba(X)
        else:
            if type(self.best_model).__name__ in ['LogisticRegression', 'SVC']:
                X_scaled = self.scaler.transform(X)
                predictions = self.best_model.predict(X_scaled)
            else:
                predictions = self.best_model.predict(X)
            probabilities = None
        
        # Decode predictions
        predictions_decoded = self.label_encoder.inverse_transform(predictions)
        
        return predictions_decoded, probabilities


def main():
    """Example usage of the AccountPredictor."""
    from data_processor import TransactionProcessor
    
    # Create sample data
    np.random.seed(42)
    n_samples = 1000
    
    sample_data = {
        'Date': pd.date_range('2024-01-01', periods=n_samples, freq='D'),
        'Description': [f'Transaction {i}' for i in range(n_samples)],
        'Amount': np.random.normal(0, 100, n_samples),
        'Account': np.random.choice(['Office', 'Utilities', 'Software', 'Revenue', 'Travel'], n_samples)
    }
    
    df = pd.DataFrame(sample_data)
    
    # Process data
    processor = TransactionProcessor()
    X, y = processor.prepare_training_data(df)
    
    # Train model
    predictor = AccountPredictor()
    X_train, X_test, X_train_scaled, X_test_scaled, y_train, y_test = predictor.prepare_data(X, y)
    
    # Train and evaluate
    predictor.train_models(X_train, X_train_scaled, y_train)
    results = predictor.evaluate_models(X_test, X_test_scaled, y_test)
    
    # Get feature importance
    importance_df = predictor.get_feature_importance(X_train)
    print("\nFeature Importance:")
    print(importance_df.head(10))


if __name__ == "__main__":
    main()

