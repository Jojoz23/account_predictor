#!/usr/bin/env python3
"""
Test script for PDF extraction functionality
Verifies that all components are working correctly
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all required libraries can be imported"""
    print("🧪 Testing imports...")
    
    required_imports = {
        'pandas': 'pandas',
        'numpy': 'numpy',
        'pdfplumber': 'pdfplumber',
        'PyPDF2': 'PyPDF2',
        'dateutil': 'python-dateutil',
        'openpyxl': 'openpyxl',
    }
    
    optional_imports = {
        'tabula': 'tabula-py',
        'camelot': 'camelot-py',
    }
    
    all_ok = True
    
    # Test required imports
    print("\n  Required libraries:")
    for module, package in required_imports.items():
        try:
            __import__(module)
            print(f"    ✅ {package}")
        except ImportError:
            print(f"    ❌ {package} - NOT INSTALLED")
            all_ok = False
    
    # Test optional imports
    print("\n  Optional libraries (failures are OK):")
    for module, package in optional_imports.items():
        try:
            __import__(module)
            print(f"    ✅ {package}")
        except ImportError:
            print(f"    ⚠️  {package} - not installed (optional)")
    
    return all_ok

def test_extraction_script():
    """Test that extraction script exists and can be imported"""
    print("\n🧪 Testing extraction scripts...")
    
    scripts = {
        'extract_bank_statements.py': 'PDF Extractor',
        'pdf_to_quickbooks.py': 'Full Pipeline',
    }
    
    all_ok = True
    
    for script, name in scripts.items():
        if os.path.exists(script):
            print(f"  ✅ {name} ({script})")
        else:
            print(f"  ❌ {name} ({script}) - NOT FOUND")
            all_ok = False
    
    return all_ok

def test_model_exists():
    """Test that the trained model exists"""
    print("\n🧪 Testing AI model...")
    
    model_path = 'models/neural_network_account_predictor.pkl'
    
    if os.path.exists(model_path):
        print(f"  ✅ AI model found ({model_path})")
        
        # Try to load it
        try:
            import joblib
            model_package = joblib.load(model_path)
            num_classes = len(model_package['class_names'])
            print(f"     Model trained on {num_classes} account categories")
            return True
        except Exception as e:
            print(f"  ⚠️  Model exists but failed to load: {e}")
            return False
    else:
        print(f"  ⚠️  AI model not found ({model_path})")
        print("     You need to train the model first:")
        print("     Run: notebooks/03_neural_network_training.ipynb")
        return False

def test_wordninja():
    """Test WordNinja for text splitting"""
    print("\n🧪 Testing WordNinja (for text processing)...")
    
    try:
        import wordninja
        test_text = "WALMARTPURCHASE"
        result = wordninja.split(test_text)
        print(f"  ✅ WordNinja working")
        print(f"     Test: '{test_text}' → {result}")
        return True
    except ImportError:
        print("  ❌ WordNinja not installed")
        return False
    except Exception as e:
        print(f"  ⚠️  WordNinja error: {e}")
        return False

def create_sample_pdf():
    """Check if there are any sample PDFs to test with"""
    print("\n🧪 Checking for sample PDFs...")
    
    # Common locations for bank statements
    sample_locations = [
        '.',
        'data',
        'statements',
        'test_data',
        'samples',
    ]
    
    found_pdfs = []
    for location in sample_locations:
        if os.path.exists(location):
            pdf_files = list(Path(location).glob('*.pdf'))
            found_pdfs.extend(pdf_files)
    
    if found_pdfs:
        print(f"  ✅ Found {len(found_pdfs)} PDF file(s):")
        for pdf in found_pdfs[:5]:  # Show first 5
            print(f"     - {pdf}")
        if len(found_pdfs) > 5:
            print(f"     ... and {len(found_pdfs) - 5} more")
        return True
    else:
        print("  ℹ️  No sample PDFs found")
        print("     To test, place a bank statement PDF in the current directory")
        return False

def run_extraction_test(pdf_path):
    """Run a test extraction on a sample PDF"""
    print(f"\n🧪 Testing extraction on: {os.path.basename(pdf_path)}")
    
    try:
        from extract_bank_statements import extract_from_pdf
        
        print("  Running extraction...")
        df = extract_from_pdf(pdf_path, save_excel=False)
        
        if df is not None and len(df) > 0:
            print(f"  ✅ Successfully extracted {len(df)} transactions")
            print(f"     Columns: {list(df.columns)}")
            print(f"\n     Sample transactions:")
            print(df.head(3).to_string(index=False))
            return True
        else:
            print("  ❌ Extraction failed - no transactions found")
            return False
            
    except Exception as e:
        print(f"  ❌ Extraction error: {e}")
        return False

def main():
    """Run all tests"""
    print("="*70)
    print("PDF EXTRACTION SYSTEM - TEST SUITE")
    print("="*70)
    
    results = {}
    
    # Run tests
    results['imports'] = test_imports()
    results['scripts'] = test_extraction_script()
    results['model'] = test_model_exists()
    results['wordninja'] = test_wordninja()
    results['pdfs'] = create_sample_pdf()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test.upper()}")
    
    print("\n" + "="*70)
    
    if all(results.values()):
        print("✅ ALL TESTS PASSED!")
        print("\nYour system is ready for PDF extraction.")
        print("\nNext steps:")
        print("1. Place a bank statement PDF in the current directory")
        print("2. Run: python extract_bank_statements.py <your_pdf_file>")
        print("3. Or run the full pipeline: python pdf_to_quickbooks.py <your_pdf_file>")
    else:
        print(f"⚠️  {total - passed} of {total} tests failed")
        print("\nPlease fix the issues above before proceeding.")
        
        if not results['imports']:
            print("\n🔧 To fix missing libraries:")
            print("   Run: python setup_pdf_extraction.py")
            print("   Or: pip install -r requirements.txt")
        
        if not results['model']:
            print("\n🔧 To create the AI model:")
            print("   Run the notebook: notebooks/03_neural_network_training.ipynb")
    
    print("="*70)
    
    # If PDF found, offer to test extraction
    if results['pdfs'] and results['imports'] and results['scripts']:
        # Find first PDF
        for location in ['.', 'data', 'statements']:
            if os.path.exists(location):
                pdfs = list(Path(location).glob('*.pdf'))
                if pdfs:
                    print(f"\n🎯 Would you like to test extraction? (Found: {pdfs[0].name})")
                    response = input("Test now? (y/n): ").lower().strip()
                    if response == 'y':
                        run_extraction_test(str(pdfs[0]))
                    break

if __name__ == '__main__':
    main()


