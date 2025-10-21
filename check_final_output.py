#!/usr/bin/env python3
"""
Check the final Excel output for Holland Leasing transactions
"""

import pandas as pd
import os

def check_final_output():
    print("🔍 CHECKING FINAL EXCEL OUTPUT")
    print("="*50)
    
    excel_path = "data/categorized_1. Jan 31st 2022.xlsx"
    
    if not os.path.exists(excel_path):
        print(f"❌ Excel file not found: {excel_path}")
        return
    
    # Read the Excel file
    df = pd.read_excel(excel_path)
    print(f"📊 Total transactions in Excel: {len(df)}")
    
    # Check Holland Leasing transactions
    holland = df[df['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    print(f"\n🏢 Holland Leasing transactions in Excel: {len(holland)}")
    
    if len(holland) > 0:
        print(f"\n📋 Holland Leasing transactions:")
        for i, (_, row) in enumerate(holland.iterrows()):
            print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
            print(f"     Description: {row.get('Description', 'N/A')}")
            print(f"     Debit: {row.get('Debit', 'N/A')}")
            print(f"     Deposit: {row.get('Deposit', 'N/A')}")
            print(f"     Category: {row.get('Category', 'N/A')}")
            print()
    
    # Check Jan 21 specifically
    jan21 = df[df['Date'].astype(str).str.contains('2022-01-21', na=False)]
    print(f"\n📅 Jan 21 transactions in Excel: {len(jan21)}")
    
    jan21_holland = jan21[jan21['Description'].str.contains('HOLAND LEASING', case=False, na=False)]
    print(f"Jan 21 Holland Leasing in Excel: {len(jan21_holland)}")
    
    if len(jan21_holland) > 0:
        print(f"\n📋 Jan 21 Holland Leasing transactions:")
        for i, (_, row) in enumerate(jan21_holland.iterrows()):
            print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
            print(f"     Description: {row.get('Description', 'N/A')}")
            print(f"     Debit: {row.get('Debit', 'N/A')}")
            print(f"     Deposit: {row.get('Deposit', 'N/A')}")
            print(f"     Category: {row.get('Category', 'N/A')}")
            print()
    
    # Check for any duplicates in the Excel
    print(f"\n🔍 Checking for duplicates in Excel...")
    duplicate_subset = ['Date', 'Description', 'Debit', 'Deposit']
    duplicates = df[df.duplicated(subset=duplicate_subset, keep=False)]
    print(f"Duplicate rows in Excel: {len(duplicates)}")
    
    if len(duplicates) > 0:
        print(f"\n📋 Duplicate transactions:")
        for i, (_, row) in enumerate(duplicates.head(10).iterrows()):
            print(f"  {i+1}. Date: {row.get('Date', 'N/A')}")
            print(f"     Description: {row.get('Description', 'N/A')}")
            print(f"     Debit: {row.get('Debit', 'N/A')}")
            print(f"     Deposit: {row.get('Deposit', 'N/A')}")
            print()

if __name__ == "__main__":
    check_final_output()

