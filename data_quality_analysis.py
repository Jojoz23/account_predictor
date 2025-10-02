#!/usr/bin/env python3
"""
Data Quality Analysis and LLM Fine-tuning Exploration
Analyzes the current dataset and explores LLM fine-tuning options
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import re
import warnings
warnings.filterwarnings('ignore')

def analyze_data_quality():
    """Analyze the quality of the current dataset"""
    print("DATA QUALITY ANALYSIS")
    print("="*50)
    
    # Load the training data
    try:
        df = pd.read_csv('data/data_template.csv')
        print(f"Loaded {len(df)} training samples")
    except FileNotFoundError:
        print("ERROR: Training data not found!")
        return None
    
    print(f"\n1. DATASET OVERVIEW:")
    print("-" * 20)
    print(f"Total samples: {len(df)}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
    print(f"Unique accounts: {df['Account'].nunique()}")
    
    # Class distribution analysis
    print(f"\n2. CLASS DISTRIBUTION ANALYSIS:")
    print("-" * 30)
    class_counts = df['Account'].value_counts()
    print(f"Most common categories:")
    for account, count in class_counts.head(10).items():
        percentage = (count / len(df)) * 100
        print(f"  {account}: {count} ({percentage:.1f}%)")
    
    print(f"\nLeast common categories:")
    for account, count in class_counts.tail(10).items():
        percentage = (count / len(df)) * 100
        print(f"  {account}: {count} ({percentage:.1f}%)")
    
    # Imbalance analysis
    print(f"\n3. CLASS IMBALANCE ANALYSIS:")
    print("-" * 30)
    max_count = class_counts.max()
    min_count = class_counts.min()
    imbalance_ratio = max_count / min_count
    
    print(f"Imbalance ratio: {imbalance_ratio:.1f}:1")
    print(f"Largest class: {class_counts.index[0]} ({max_count} samples)")
    print(f"Smallest class: {class_counts.index[-1]} ({min_count} samples)")
    
    # Classes with very few samples
    few_samples = class_counts[class_counts < 10]
    print(f"\nClasses with <10 samples: {len(few_samples)}")
    for account, count in few_samples.items():
        print(f"  {account}: {count} samples")
    
    # Description quality analysis
    print(f"\n4. DESCRIPTION QUALITY ANALYSIS:")
    print("-" * 35)
    
    # Length analysis
    df['Description_Length'] = df['Description'].str.len()
    print(f"Average description length: {df['Description_Length'].mean():.1f} characters")
    print(f"Min description length: {df['Description_Length'].min()}")
    print(f"Max description length: {df['Description_Length'].max()}")
    
    # Very short descriptions
    short_descriptions = df[df['Description_Length'] < 5]
    print(f"Very short descriptions (<5 chars): {len(short_descriptions)}")
    if len(short_descriptions) > 0:
        print("Examples:")
        for desc in short_descriptions['Description'].head(5):
            print(f"  '{desc}'")
    
    # Duplicate descriptions
    duplicate_descriptions = df['Description'].value_counts()
    high_freq_descriptions = duplicate_descriptions[duplicate_descriptions > 10]
    print(f"\nHigh frequency descriptions (>10 occurrences): {len(high_freq_descriptions)}")
    for desc, count in high_freq_descriptions.head(5).items():
        print(f"  '{desc}': {count} times")
    
    # Amount analysis
    print(f"\n5. AMOUNT ANALYSIS:")
    print("-" * 18)
    
    # Clean amount column
    df['Amount_Clean'] = df['Amount'].astype(str).str.replace(',', '').str.replace(' ', '')
    df['Amount_Clean'] = pd.to_numeric(df['Amount_Clean'], errors='coerce')
    
    print(f"Amount range: ${df['Amount_Clean'].min():.2f} to ${df['Amount_Clean'].max():.2f}")
    print(f"Average amount: ${df['Amount_Clean'].mean():.2f}")
    print(f"Median amount: ${df['Amount_Clean'].median():.2f}")
    
    # Zero amounts
    zero_amounts = df[df['Amount_Clean'] == 0]
    print(f"Zero amounts: {len(zero_amounts)}")
    
    # Very small amounts
    small_amounts = df[(df['Amount_Clean'] > 0) & (df['Amount_Clean'] < 1)]
    print(f"Very small amounts (<$1): {len(small_amounts)}")
    
    # Data quality issues
    print(f"\n6. DATA QUALITY ISSUES:")
    print("-" * 25)
    
    issues = []
    
    # Missing values
    missing_values = df.isnull().sum()
    if missing_values.any():
        issues.append(f"Missing values: {missing_values.sum()} total")
    
    # Duplicate rows
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        issues.append(f"Duplicate rows: {duplicates}")
    
    # Inconsistent account names
    account_variations = {
        'Bank Charges': ['Bank Charges', 'Bank charges'],
        'Office Expense': ['Office Expense', 'Office expense'],
        'Due to shareholder': ['Due to Shareholder', 'Due to shareholder']
    }
    
    for base_name, variations in account_variations.items():
        if all(var in class_counts.index for var in variations):
            issues.append(f"Inconsistent naming: {variations}")
    
    if issues:
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("  No major data quality issues detected")
    
    return df, class_counts

def explore_llm_options():
    """Explore LLM fine-tuning options"""
    print(f"\n" + "="*60)
    print("LARGE LANGUAGE MODEL FINE-TUNING OPTIONS")
    print("="*60)
    
    print(f"\n1. RECOMMENDED LLM MODELS:")
    print("-" * 30)
    
    models = [
        {
            "name": "Llama 3.1 8B",
            "size": "8B parameters",
            "cost": "Low",
            "performance": "Good",
            "fine_tuning": "Easy",
            "description": "Best balance of performance and cost"
        },
        {
            "name": "Mistral 7B",
            "size": "7B parameters", 
            "cost": "Low",
            "performance": "Good",
            "fine_tuning": "Easy",
            "description": "Fast and efficient, good for classification"
        },
        {
            "name": "Code Llama 7B",
            "size": "7B parameters",
            "cost": "Low", 
            "performance": "Very Good",
            "fine_tuning": "Easy",
            "description": "Excellent for structured data understanding"
        },
        {
            "name": "Llama 3.1 70B",
            "size": "70B parameters",
            "cost": "High",
            "performance": "Excellent",
            "fine_tuning": "Moderate",
            "description": "Best performance but expensive"
        }
    ]
    
    for model in models:
        print(f"\n{model['name']}:")
        print(f"  Size: {model['size']}")
        print(f"  Cost: {model['cost']}")
        print(f"  Performance: {model['performance']}")
        print(f"  Fine-tuning: {model['fine_tuning']}")
        print(f"  Description: {model['description']}")
    
    print(f"\n2. FINE-TUNING APPROACHES:")
    print("-" * 30)
    
    approaches = [
        {
            "name": "Supervised Fine-tuning (SFT)",
            "description": "Train on transaction descriptions → account categories",
            "data_needed": "4,000+ examples",
            "time": "2-4 hours",
            "cost": "$5-20",
            "best_for": "Direct classification"
        },
        {
            "name": "LoRA (Low-Rank Adaptation)",
            "description": "Efficient fine-tuning with minimal parameters",
            "data_needed": "2,000+ examples", 
            "time": "1-2 hours",
            "cost": "$2-10",
            "best_for": "Quick experimentation"
        },
        {
            "name": "QLoRA (Quantized LoRA)",
            "description": "Memory-efficient LoRA with quantization",
            "data_needed": "2,000+ examples",
            "time": "1-2 hours", 
            "cost": "$1-5",
            "best_for": "Limited resources"
        },
        {
            "name": "Few-shot Prompting",
            "description": "Use examples in prompts without fine-tuning",
            "data_needed": "50-100 examples",
            "time": "Minutes",
            "cost": "$0.10-1",
            "best_for": "Quick testing"
        }
    ]
    
    for approach in approaches:
        print(f"\n{approach['name']}:")
        print(f"  Description: {approach['description']}")
        print(f"  Data needed: {approach['data_needed']}")
        print(f"  Time: {approach['time']}")
        print(f"  Cost: {approach['cost']}")
        print(f"  Best for: {approach['best_for']}")
    
    print(f"\n3. DATA PREPARATION FOR LLM:")
    print("-" * 30)
    
    print("Format: JSONL (JSON Lines)")
    print("Example format:")
    print("""
{"instruction": "Classify this transaction into the appropriate account category.", "input": "STARBUCKS COFFEE -7.42", "output": "Meals and Entertainment"}
{"instruction": "Classify this transaction into the appropriate account category.", "input": "COSTCO WHOLESALE -400.99", "output": "Office Supplies"}
{"instruction": "Classify this transaction into the appropriate account category.", "input": "PRE-AUTH PYMT - OTFS FEE BPY -40", "output": "Bank Charges"}
    """)
    
    print(f"\n4. EXPECTED IMPROVEMENTS WITH LLM:")
    print("-" * 35)
    
    improvements = [
        "Better understanding of transaction context",
        "Improved handling of ambiguous descriptions", 
        "More nuanced classification decisions",
        "Better generalization to new transaction types",
        "Higher confidence scores for correct predictions",
        "Reduced over-prediction of common categories"
    ]
    
    for improvement in improvements:
        print(f"  ✓ {improvement}")
    
    print(f"\n5. IMPLEMENTATION RECOMMENDATION:")
    print("-" * 35)
    print("1. Start with Few-shot Prompting (quick test)")
    print("2. If promising, try LoRA fine-tuning")
    print("3. Use Code Llama 7B for best balance")
    print("4. Prepare 2,000+ high-quality examples")
    print("5. Compare with current models on test set")

def create_llm_training_data(df):
    """Create training data in LLM format"""
    print(f"\n" + "="*50)
    print("CREATING LLM TRAINING DATA")
    print("="*50)
    
    # Clean the data
    df_clean = df.copy()
    df_clean['Amount_Clean'] = df_clean['Amount'].astype(str).str.replace(',', '').str.replace(' ', '')
    df_clean['Amount_Clean'] = pd.to_numeric(df_clean['Amount_Clean'], errors='coerce')
    
    # Remove rows with missing data
    df_clean = df_clean.dropna(subset=['Description', 'Account', 'Amount_Clean'])
    
    # Create training examples
    training_examples = []
    
    for _, row in df_clean.iterrows():
        # Format: "DESCRIPTION AMOUNT"
        input_text = f"{row['Description']} {row['Amount_Clean']}"
        
        example = {
            "instruction": "Classify this transaction into the appropriate account category.",
            "input": input_text,
            "output": row['Account']
        }
        training_examples.append(example)
    
    # Save as JSONL
    import json
    with open('llm_training_data.jsonl', 'w') as f:
        for example in training_examples:
            f.write(json.dumps(example) + '\n')
    
    print(f"Created {len(training_examples)} training examples")
    print("Saved as 'llm_training_data.jsonl'")
    
    # Show sample examples
    print(f"\nSample training examples:")
    for i, example in enumerate(training_examples[:5]):
        print(f"{i+1}. Input: {example['input']}")
        print(f"   Output: {example['output']}")
        print()
    
    return training_examples

def main():
    """Main analysis function"""
    print("ACCOUNT PREDICTION MODEL ANALYSIS")
    print("="*50)
    
    # Analyze current data quality
    result = analyze_data_quality()
    if result is None:
        return
    
    df, class_counts = result
    
    # Explore LLM options
    explore_llm_options()
    
    # Create LLM training data
    training_examples = create_llm_training_data(df)
    
    print(f"\n" + "="*60)
    print("SUMMARY AND RECOMMENDATIONS")
    print("="*60)
    
    print(f"\nCURRENT MODEL ISSUES:")
    print("-" * 20)
    print("1. Class imbalance (423 Sales vs 16 Cash)")
    print("2. Inconsistent naming (Bank Charges vs Bank charges)")
    print("3. Random Forest over-predicts Sales (83.7%)")
    print("4. Low confidence scores (RF: 24.2% avg)")
    print("5. Limited context understanding")
    
    print(f"\nRECOMMENDED NEXT STEPS:")
    print("-" * 25)
    print("1. Try few-shot prompting with GPT-4 or Claude")
    print("2. Fine-tune Code Llama 7B with LoRA")
    print("3. Clean up class naming inconsistencies")
    print("4. Add more diverse training examples")
    print("5. Use ensemble of LLM + traditional models")

if __name__ == "__main__":
    main()
