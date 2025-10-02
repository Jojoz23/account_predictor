#!/usr/bin/env python3
"""
Quick Data Quality Analysis
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def analyze_data():
    """Quick analysis of the current dataset"""
    print("QUICK DATA QUALITY ANALYSIS")
    print("="*40)
    
    # Load the training data with different encodings
    try:
        df = pd.read_csv('data/data_template.csv', encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv('data/data_template.csv', encoding='latin-1')
        except:
            df = pd.read_csv('data/data_template.csv', encoding='cp1252')
    
    print(f"Loaded {len(df)} training samples")
    
    # Basic info
    print(f"\n1. DATASET OVERVIEW:")
    print(f"Total samples: {len(df)}")
    print(f"Unique accounts: {df['Account'].nunique()}")
    
    # Class distribution
    class_counts = df['Account'].value_counts()
    print(f"\n2. CLASS DISTRIBUTION:")
    print("Top 10 categories:")
    for account, count in class_counts.head(10).items():
        percentage = (count / len(df)) * 100
        print(f"  {account}: {count} ({percentage:.1f}%)")
    
    print("\nBottom 10 categories:")
    for account, count in class_counts.tail(10).items():
        percentage = (count / len(df)) * 100
        print(f"  {account}: {count} ({percentage:.1f}%)")
    
    # Imbalance analysis
    max_count = class_counts.max()
    min_count = class_counts.min()
    imbalance_ratio = max_count / min_count
    
    print(f"\n3. IMBALANCE ANALYSIS:")
    print(f"Imbalance ratio: {imbalance_ratio:.1f}:1")
    print(f"Largest class: {class_counts.index[0]} ({max_count} samples)")
    print(f"Smallest class: {class_counts.index[-1]} ({min_count} samples)")
    
    # Classes with very few samples
    few_samples = class_counts[class_counts < 10]
    print(f"\nClasses with <10 samples: {len(few_samples)}")
    for account, count in few_samples.items():
        print(f"  {account}: {count} samples")
    
    # Description analysis
    df['Description_Length'] = df['Description'].str.len()
    print(f"\n4. DESCRIPTION ANALYSIS:")
    print(f"Average length: {df['Description_Length'].mean():.1f} chars")
    print(f"Min length: {df['Description_Length'].min()}")
    print(f"Max length: {df['Description_Length'].max()}")
    
    # Very short descriptions
    short_descriptions = df[df['Description_Length'] < 5]
    print(f"Very short descriptions (<5 chars): {len(short_descriptions)}")
    
    # Duplicate descriptions
    duplicate_descriptions = df['Description'].value_counts()
    high_freq = duplicate_descriptions[duplicate_descriptions > 10]
    print(f"High frequency descriptions (>10x): {len(high_freq)}")
    
    # Data quality issues
    print(f"\n5. DATA QUALITY ISSUES:")
    
    issues = []
    
    # Inconsistent naming
    if 'Bank Charges' in class_counts.index and 'Bank charges' in class_counts.index:
        issues.append("Inconsistent naming: 'Bank Charges' vs 'Bank charges'")
    
    if 'Office Expense' in class_counts.index and 'Office expense' in class_counts.index:
        issues.append("Inconsistent naming: 'Office Expense' vs 'Office expense'")
    
    if 'Due to Shareholder' in class_counts.index and 'Due to shareholder' in class_counts.index:
        issues.append("Inconsistent naming: 'Due to Shareholder' vs 'Due to shareholder'")
    
    if issues:
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("  No major naming inconsistencies found")
    
    return df, class_counts

def explore_llm_solutions():
    """Explore LLM solutions"""
    print(f"\n" + "="*50)
    print("LLM FINE-TUNING SOLUTIONS")
    print("="*50)
    
    print(f"\n1. WHY LLMs MIGHT BE BETTER:")
    print("-" * 30)
    reasons = [
        "Better understanding of transaction context",
        "Can handle ambiguous descriptions better", 
        "More nuanced classification decisions",
        "Better generalization to new transaction types",
        "Higher confidence for correct predictions",
        "Reduced over-prediction of common categories"
    ]
    
    for reason in reasons:
        print(f"  ✓ {reason}")
    
    print(f"\n2. RECOMMENDED MODELS:")
    print("-" * 25)
    
    models = [
        ("Code Llama 7B", "Best for structured data, good balance"),
        ("Mistral 7B", "Fast and efficient, good performance"),
        ("Llama 3.1 8B", "Good general performance"),
        ("GPT-4 (few-shot)", "Best performance, no fine-tuning needed")
    ]
    
    for model, description in models:
        print(f"  • {model}: {description}")
    
    print(f"\n3. FINE-TUNING APPROACHES:")
    print("-" * 30)
    
    approaches = [
        ("Few-shot Prompting", "50-100 examples, $0.10-1", "Quick test"),
        ("LoRA Fine-tuning", "2,000+ examples, $2-10", "Best balance"),
        ("QLoRA", "2,000+ examples, $1-5", "Memory efficient"),
        ("Full Fine-tuning", "4,000+ examples, $5-20", "Best performance")
    ]
    
    for approach, cost, best_for in approaches:
        print(f"  • {approach}: {cost} - {best_for}")
    
    print(f"\n4. IMPLEMENTATION STEPS:")
    print("-" * 25)
    steps = [
        "1. Clean up class naming inconsistencies",
        "2. Create 2,000+ high-quality training examples", 
        "3. Try few-shot prompting with GPT-4 first",
        "4. If promising, fine-tune Code Llama 7B with LoRA",
        "5. Compare with current models on test set"
    ]
    
    for step in steps:
        print(f"  {step}")

def main():
    """Main analysis"""
    # Analyze current data
    df, class_counts = analyze_data()
    
    # Explore LLM solutions
    explore_llm_solutions()
    
    print(f"\n" + "="*50)
    print("RECOMMENDATIONS")
    print("="*50)
    
    print(f"\nIMMEDIATE ACTIONS:")
    print("1. Fix naming inconsistencies (Bank Charges vs Bank charges)")
    print("2. Try few-shot prompting with GPT-4 or Claude")
    print("3. If promising, fine-tune Code Llama 7B")
    
    print(f"\nEXPECTED IMPROVEMENTS:")
    print("• Better context understanding")
    print("• More balanced predictions") 
    print("• Higher confidence scores")
    print("• Better handling of edge cases")

if __name__ == "__main__":
    main()
