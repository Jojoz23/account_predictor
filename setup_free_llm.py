#!/usr/bin/env python3
"""
Free LLM Setup Script for Account Prediction
Sets up free LLM options for account classification
"""

import subprocess
import sys
import os

def install_ollama():
    """Install Ollama if not already installed"""
    print("🦙 SETTING UP OLLAMA")
    print("="*25)
    
    try:
        # Check if Ollama is already installed
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama is already installed!")
            print(f"Version: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Ollama not found. Please install it manually:")
    print("\n1. Go to https://ollama.ai")
    print("2. Download Ollama for your operating system")
    print("3. Install it")
    print("4. Run this script again")
    
    return False

def pull_models():
    """Pull recommended models"""
    print("\n📥 PULLING RECOMMENDED MODELS")
    print("="*35)
    
    models = [
        ("codellama:7b", "Best for accounting (structured data)"),
        ("llama3.1:8b", "Good general performance"),
        ("mistral:7b", "Fast and efficient")
    ]
    
    for model, description in models:
        print(f"\nPulling {model}...")
        print(f"Description: {description}")
        
        try:
            result = subprocess.run(['ollama', 'pull', model], 
                                  capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ {model} pulled successfully!")
            else:
                print(f"❌ Failed to pull {model}: {result.stderr}")
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout pulling {model} (this is normal for large models)")
        except Exception as e:
            print(f"❌ Error pulling {model}: {e}")

def test_models():
    """Test the pulled models"""
    print("\n🧪 TESTING MODELS")
    print("="*20)
    
    try:
        # List available models
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            print("Available models:")
            print(result.stdout)
        else:
            print("❌ Could not list models")
            return
    except Exception as e:
        print(f"❌ Error listing models: {e}")
        return
    
    # Test with a simple query
    test_models = ['codellama:7b', 'llama3.1:8b', 'mistral:7b']
    
    for model in test_models:
        print(f"\nTesting {model}...")
        try:
            # Test with a simple accounting question
            test_prompt = "Classify this transaction: STARBUCKS COFFEE -7.42"
            
            result = subprocess.run([
                'ollama', 'run', model, test_prompt
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"✅ {model} working!")
                print(f"Response: {result.stdout.strip()[:100]}...")
            else:
                print(f"❌ {model} failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {model} timed out (this is normal)")
        except Exception as e:
            print(f"❌ Error testing {model}: {e}")

def create_batch_predictor():
    """Create a batch predictor using Ollama"""
    print("\n📝 CREATING BATCH PREDICTOR")
    print("="*30)
    
    batch_predictor_code = '''#!/usr/bin/env python3
"""
Free LLM Batch Predictor using Ollama
"""

import ollama
import pandas as pd
import json
import time

def classify_transaction(description, amount, examples, model="codellama:7b"):
    """Classify a single transaction using Ollama"""
    try:
        # Create examples string
        examples_str = "\\n".join([
            f"Transaction: {ex['description']} {ex['amount']} → Account: {ex['account']}"
            for ex in examples
        ])
        
        prompt = f"""You are an expert accountant. Classify transactions into account categories.

Examples:
{examples_str}

Classify this transaction:
Transaction: {description} {amount}
Account:"""
        
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert accountant who classifies transactions into appropriate account categories. Always respond with just the account name."},
                {"role": "user", "content": prompt}
            ],
            options={
                "temperature": 0.1,
                "top_p": 0.9,
                "max_tokens": 50
            }
        )
        
        result = response['message']['content'].strip()
        
        # Clean up the response
        if "Account:" in result:
            result = result.split("Account:")[-1].strip()
        
        return result.split('\\n')[0].strip()
    
    except Exception as e:
        print(f"Error: {e}")
        return "Error"

def predict_batch(input_file, output_file=None, model="codellama:7b"):
    """Predict account categories for a batch of transactions"""
    
    print("🆓 FREE LLM BATCH PREDICTOR")
    print("="*35)
    
    # Load data
    try:
        if input_file.endswith('.xlsx'):
            df = pd.read_excel(input_file)
        elif input_file.endswith('.csv'):
            df = pd.read_csv(input_file)
        else:
            print("❌ Unsupported file format")
            return
        
        print(f"✅ Loaded {len(df)} transactions")
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # Create few-shot examples
    examples = [
        {"description": "STARBUCKS COFFEE", "amount": "-7.42", "account": "Meals and Entertainment"},
        {"description": "COSTCO WHOLESALE", "amount": "-400.99", "account": "Office Supplies"},
        {"description": "PRE-AUTH PYMT - OTFS FEE BPY", "amount": "-40", "account": "Bank Charges"},
        {"description": "INTEREST", "amount": "-0.04", "account": "Bank Charges"},
        {"description": "TRANSFER 50356SF01OB3", "amount": "-9234.33", "account": "Transfer Between Banks"}
    ]
    
    # Make predictions
    predictions = []
    print("\\nMaking predictions...")
    
    for i, row in df.iterrows():
        desc = str(row['Description'])
        amount = str(row['Amount'])
        
        prediction = classify_transaction(desc, amount, examples, model)
        predictions.append(prediction)
        
        if (i + 1) % 10 == 0:
            print(f"Processed {i + 1}/{len(df)} transactions...")
        
        time.sleep(0.1)  # Small delay to avoid overwhelming
    
    # Add predictions to dataframe
    df['LLM_Predicted_Account'] = predictions
    
    # Save results
    if output_file is None:
        output_file = input_file.replace('.xlsx', '_llm_predicted.xlsx').replace('.csv', '_llm_predicted.csv')
    
    try:
        if output_file.endswith('.xlsx'):
            df.to_excel(output_file, index=False)
        else:
            df.to_csv(output_file, index=False)
        
        print(f"\\n✅ Results saved to: {output_file}")
        print(f"✅ Processed {len(df)} transactions")
        
        # Show prediction distribution
        pred_counts = df['LLM_Predicted_Account'].value_counts()
        print("\\nPrediction distribution:")
        for account, count in pred_counts.head(10).items():
            print(f"  {account}: {count}")
            
    except Exception as e:
        print(f"❌ Error saving results: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python free_llm_predictor.py <input_file> [output_file] [model]")
        print("Example: python free_llm_predictor.py data/transactions.xlsx")
        print("Models: codellama:7b, llama3.1:8b, mistral:7b")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    model = sys.argv[3] if len(sys.argv) > 3 else "codellama:7b"
    
    predict_batch(input_file, output_file, model)
'''
    
    with open('free_llm_predictor.py', 'w') as f:
        f.write(batch_predictor_code)
    
    print("✅ Created free_llm_predictor.py")
    print("Usage: python free_llm_predictor.py data/Bookkeeping 2025.xlsx")

def main():
    """Main setup function"""
    print("🆓 FREE LLM SETUP FOR ACCOUNT PREDICTION")
    print("="*45)
    
    # Check if Ollama is installed
    if not install_ollama():
        return
    
    # Pull recommended models
    pull_models()
    
    # Test models
    test_models()
    
    # Create batch predictor
    create_batch_predictor()
    
    print("\n🎉 SETUP COMPLETE!")
    print("="*20)
    print("You can now use free LLMs for account prediction!")
    print("\nNext steps:")
    print("1. Run: python free_llm_predictor.py data/Bookkeeping 2025.xlsx")
    print("2. Compare results with traditional models")
    print("3. Fine-tune if needed")

if __name__ == "__main__":
    main()
