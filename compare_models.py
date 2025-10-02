#!/usr/bin/env python3
"""
Model Comparison Script
Compares Neural Network vs Random Forest predictions on the same dataset
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

def load_predictions():
    """Load both model predictions"""
    print("Loading prediction results...")
    
    # Load Neural Network predictions
    try:
        nn_df = pd.read_excel('data/Bookkeeping 2025_predicted.xlsx')
        print(f"Neural Network predictions loaded: {len(nn_df)} transactions")
    except FileNotFoundError:
        print("ERROR: Neural Network predictions not found. Run batch_predict_simple.py first.")
        return None, None
    
    # Load Random Forest predictions
    try:
        rf_df = pd.read_excel('data/Bookkeeping 2025_rf_predicted.xlsx')
        print(f"Random Forest predictions loaded: {len(rf_df)} transactions")
    except FileNotFoundError:
        print("ERROR: Random Forest predictions not found. Run batch_predict_rf.py first.")
        return None, None
    
    return nn_df, rf_df

def compare_models(nn_df, rf_df):
    """Compare the two models"""
    print("\n" + "="*60)
    print("MODEL COMPARISON ANALYSIS")
    print("="*60)
    
    # Basic statistics
    print("\n1. BASIC STATISTICS:")
    print("-" * 30)
    print(f"Neural Network - Average Confidence: {nn_df['Confidence'].mean():.1%}")
    print(f"Random Forest  - Average Confidence: {rf_df['RF_Confidence'].mean():.1%}")
    print(f"Neural Network - Min Confidence: {nn_df['Confidence'].min():.1%}")
    print(f"Random Forest  - Min Confidence: {rf_df['RF_Confidence'].min():.1%}")
    print(f"Neural Network - Max Confidence: {nn_df['Confidence'].max():.1%}")
    print(f"Random Forest  - Max Confidence: {rf_df['RF_Confidence'].max():.1%}")
    
    # Prediction distribution comparison
    print("\n2. PREDICTION DISTRIBUTION COMPARISON:")
    print("-" * 40)
    
    nn_counts = nn_df['Predicted_Account'].value_counts()
    rf_counts = rf_df['RF_Predicted_Account'].value_counts()
    
    # Get all unique accounts from both models
    all_accounts = set(nn_counts.index) | set(rf_counts.index)
    
    print(f"{'Account':<25} {'Neural Net':<12} {'Random Forest':<12} {'Difference':<12}")
    print("-" * 65)
    
    for account in sorted(all_accounts):
        nn_count = nn_counts.get(account, 0)
        rf_count = rf_counts.get(account, 0)
        diff = nn_count - rf_count
        print(f"{account:<25} {nn_count:<12} {rf_count:<12} {diff:>+11}")
    
    # Agreement analysis
    print("\n3. MODEL AGREEMENT ANALYSIS:")
    print("-" * 30)
    
    # Merge dataframes to compare predictions
    comparison_df = nn_df[['Description', 'Amount', 'Predicted_Account', 'Confidence']].copy()
    comparison_df = comparison_df.merge(
        rf_df[['Description', 'Amount', 'RF_Predicted_Account', 'RF_Confidence']], 
        on=['Description', 'Amount'], 
        how='inner'
    )
    
    # Calculate agreement
    agreement = (comparison_df['Predicted_Account'] == comparison_df['RF_Predicted_Account']).mean()
    print(f"Exact Agreement: {agreement:.1%} ({agreement * len(comparison_df):.0f} out of {len(comparison_df)} transactions)")
    
    # High confidence agreement
    high_conf_nn = comparison_df['Confidence'] > 0.8
    high_conf_rf = comparison_df['RF_Confidence'] > 0.8
    high_conf_both = high_conf_nn & high_conf_rf
    
    if high_conf_both.sum() > 0:
        high_conf_agreement = (comparison_df.loc[high_conf_both, 'Predicted_Account'] == 
                             comparison_df.loc[high_conf_both, 'RF_Predicted_Account']).mean()
        print(f"High Confidence Agreement (>80%): {high_conf_agreement:.1%} ({high_conf_agreement * high_conf_both.sum():.0f} out of {high_conf_both.sum()} transactions)")
    
    # Disagreement analysis
    print("\n4. DISAGREEMENT ANALYSIS:")
    print("-" * 25)
    
    disagreements = comparison_df[comparison_df['Predicted_Account'] != comparison_df['RF_Predicted_Account']]
    print(f"Total Disagreements: {len(disagreements)} ({len(disagreements)/len(comparison_df):.1%})")
    
    if len(disagreements) > 0:
        print("\nTop Disagreement Patterns:")
        disagreement_patterns = disagreements.groupby(['Predicted_Account', 'RF_Predicted_Account']).size().sort_values(ascending=False)
        for (nn_pred, rf_pred), count in disagreement_patterns.head(10).items():
            print(f"  NN: {nn_pred} vs RF: {rf_pred} - {count} cases")
    
    # Confidence distribution comparison
    print("\n5. CONFIDENCE DISTRIBUTION:")
    print("-" * 30)
    
    conf_ranges = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
    
    print(f"{'Confidence Range':<15} {'Neural Net':<12} {'Random Forest':<12}")
    print("-" * 40)
    
    for low, high in conf_ranges:
        nn_in_range = ((nn_df['Confidence'] >= low) & (nn_df['Confidence'] < high)).sum()
        rf_in_range = ((rf_df['RF_Confidence'] >= low) & (rf_df['RF_Confidence'] < high)).sum()
        print(f"{low:.1f}-{high:.1f}:{'':<6} {nn_in_range:<12} {rf_in_range:<12}")
    
    # Sample disagreements
    print("\n6. SAMPLE DISAGREEMENTS:")
    print("-" * 25)
    
    if len(disagreements) > 0:
        sample_disagreements = disagreements.head(5)
        for i, (_, row) in enumerate(sample_disagreements.iterrows(), 1):
            print(f"{i}. {row['Description']} (${row['Amount']})")
            print(f"   Neural Net: {row['Predicted_Account']} ({row['Confidence']:.1%})")
            print(f"   Random Forest: {row['RF_Predicted_Account']} ({row['RF_Confidence']:.1%})")
            print()
    
    return comparison_df

def create_comparison_plots(comparison_df):
    """Create comparison visualizations"""
    print("\n7. CREATING COMPARISON PLOTS...")
    print("-" * 30)
    
    try:
        # Set up the plotting style
        plt.style.use('default')
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Neural Network vs Random Forest Model Comparison', fontsize=16, fontweight='bold')
        
        # 1. Confidence Distribution Comparison
        axes[0, 0].hist(comparison_df['Confidence'], bins=20, alpha=0.7, label='Neural Network', color='blue')
        axes[0, 0].hist(comparison_df['RF_Confidence'], bins=20, alpha=0.7, label='Random Forest', color='red')
        axes[0, 0].set_xlabel('Confidence Score')
        axes[0, 0].set_ylabel('Frequency')
        axes[0, 0].set_title('Confidence Distribution Comparison')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Agreement vs Confidence
        agreement = comparison_df['Predicted_Account'] == comparison_df['RF_Predicted_Account']
        axes[0, 1].scatter(comparison_df['Confidence'], comparison_df['RF_Confidence'], 
                          c=agreement, cmap='RdYlGn', alpha=0.6)
        axes[0, 1].set_xlabel('Neural Network Confidence')
        axes[0, 1].set_ylabel('Random Forest Confidence')
        axes[0, 1].set_title('Confidence Correlation (Green=Agree, Red=Disagree)')
        axes[0, 1].plot([0, 1], [0, 1], 'k--', alpha=0.5)
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Prediction Count Comparison
        nn_counts = comparison_df['Predicted_Account'].value_counts()
        rf_counts = comparison_df['RF_Predicted_Account'].value_counts()
        
        # Get top 10 accounts
        all_accounts = set(nn_counts.index) | set(rf_counts.index)
        top_accounts = sorted(all_accounts, key=lambda x: nn_counts.get(x, 0) + rf_counts.get(x, 0), reverse=True)[:10]
        
        x = np.arange(len(top_accounts))
        width = 0.35
        
        axes[1, 0].bar(x - width/2, [nn_counts.get(acc, 0) for acc in top_accounts], 
                      width, label='Neural Network', alpha=0.8, color='blue')
        axes[1, 0].bar(x + width/2, [rf_counts.get(acc, 0) for acc in top_accounts], 
                      width, label='Random Forest', alpha=0.8, color='red')
        
        axes[1, 0].set_xlabel('Account Categories')
        axes[1, 0].set_ylabel('Number of Predictions')
        axes[1, 0].set_title('Prediction Count Comparison (Top 10)')
        axes[1, 0].set_xticks(x)
        axes[1, 0].set_xticklabels(top_accounts, rotation=45, ha='right')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Agreement Rate by Confidence Level
        conf_bins = pd.cut(comparison_df['Confidence'], bins=5, labels=['0-20%', '20-40%', '40-60%', '60-80%', '80-100%'])
        agreement_by_conf = comparison_df.groupby(conf_bins).apply(
            lambda x: (x['Predicted_Account'] == x['RF_Predicted_Account']).mean()
        )
        
        axes[1, 1].bar(range(len(agreement_by_conf)), agreement_by_conf.values, 
                      color='green', alpha=0.7)
        axes[1, 1].set_xlabel('Neural Network Confidence Range')
        axes[1, 1].set_ylabel('Agreement Rate')
        axes[1, 1].set_title('Model Agreement by Confidence Level')
        axes[1, 1].set_xticks(range(len(agreement_by_conf)))
        axes[1, 1].set_xticklabels(agreement_by_conf.index, rotation=45)
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('model_comparison.png', dpi=300, bbox_inches='tight')
        print("Comparison plots saved as 'model_comparison.png'")
        
    except Exception as e:
        print(f"Error creating plots: {e}")

def main():
    """Main comparison function"""
    print("MODEL COMPARISON TOOL")
    print("="*50)
    
    # Load predictions
    nn_df, rf_df = load_predictions()
    if nn_df is None or rf_df is None:
        return
    
    # Compare models
    comparison_df = compare_models(nn_df, rf_df)
    
    # Create visualizations
    create_comparison_plots(comparison_df)
    
    print("\n" + "="*60)
    print("COMPARISON COMPLETE!")
    print("="*60)
    print("Files generated:")
    print("- model_comparison.png (visualization)")
    print("- data/Bookkeeping 2025_predicted.xlsx (Neural Network results)")
    print("- data/Bookkeeping 2025_rf_predicted.xlsx (Random Forest results)")

if __name__ == "__main__":
    main()

