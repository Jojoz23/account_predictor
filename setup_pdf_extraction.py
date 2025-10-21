#!/usr/bin/env python3
"""
Setup script for PDF extraction dependencies
Installs all required libraries with error handling
"""

import subprocess
import sys
import platform

def install_package(package):
    """Install a single package"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("="*70)
    print("BANK STATEMENT PDF EXTRACTOR - SETUP")
    print("="*70)
    print("\nThis script will install all required dependencies.")
    print("It may take a few minutes...\n")
    
    # Core dependencies
    core_packages = [
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "openpyxl>=3.1.0",
        "python-dateutil>=2.8.0",
    ]
    
    # PDF extraction packages
    pdf_packages = [
        "pdfplumber>=0.10.0",
        "PyPDF2>=3.0.0",
    ]
    
    # Optional packages (may fail on some systems)
    optional_packages = [
        "tabula-py>=2.8.0",
        "camelot-py>=0.11.0",
    ]
    
    # AI model packages
    ai_packages = [
        "scikit-learn>=1.3.0",
        "joblib>=1.3.0",
        "wordninja>=2.0.0",
        "tensorflow>=2.13.0",
    ]
    
    print("\n📦 Installing core packages...")
    for package in core_packages:
        print(f"  Installing {package}...", end=" ")
        if install_package(package):
            print("✅")
        else:
            print("❌ FAILED")
            print(f"     Please install manually: pip install {package}")
    
    print("\n📄 Installing PDF extraction packages...")
    for package in pdf_packages:
        print(f"  Installing {package}...", end=" ")
        if install_package(package):
            print("✅")
        else:
            print("❌ FAILED")
            print(f"     Please install manually: pip install {package}")
    
    print("\n🔧 Installing optional packages (failures are OK)...")
    for package in optional_packages:
        print(f"  Installing {package}...", end=" ")
        if install_package(package):
            print("✅")
        else:
            print("⚠️  SKIPPED (optional)")
    
    print("\n🧠 Installing AI model packages...")
    for package in ai_packages:
        print(f"  Installing {package}...", end=" ")
        if install_package(package):
            print("✅")
        else:
            print("❌ FAILED")
            print(f"     Please install manually: pip install {package}")
    
    print("\n" + "="*70)
    print("✅ SETUP COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("1. Ensure your AI model is trained:")
    print("   Run: notebooks/03_neural_network_training.ipynb")
    print("\n2. Test PDF extraction:")
    print("   Run: python extract_bank_statements.py <your_pdf_file>")
    print("\n3. Or use the full pipeline:")
    print("   Run: python pdf_to_quickbooks.py <your_pdf_file>")
    print("\n" + "="*70)
    
    # System-specific notes
    if platform.system() == "Windows":
        print("\n💡 Windows users:")
        print("   If you get DLL errors with tensorflow, install:")
        print("   Microsoft Visual C++ Redistributable")
    elif platform.system() == "Darwin":
        print("\n💡 Mac users:")
        print("   If you get errors with camelot, install Ghostscript:")
        print("   brew install ghostscript")
    else:
        print("\n💡 Linux users:")
        print("   If you get errors with camelot, install:")
        print("   sudo apt-get install ghostscript python3-tk")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    main()


