import os
import sys
import glob
import re
import detector

# Import Engines
import hsbc_tagger
import banamex_tagger
import bbva_tagger
import santander
import monex_tagger
import db_tagger
import ocr_utils

def process_file(filename, bank, prefix):
    print(f"\n🚀 Processing: {filename} (Bank: {bank})")
    
    try:
        if bank == "HSBC":
            coords, actual_pdf = hsbc_tagger.get_transaction_coordinates(filename)
            if coords:
                print(f"   > Found {len(coords)} transactions.")
                hsbc_tagger.create_tagged_pdf(actual_pdf, coords, prefix)
            else:
                print("   > No transactions found.")

        elif bank == "DB":
            coords, actual_pdf = db_tagger.get_transaction_coordinates(filename)
            if coords:
                print(f"   > Found {len(coords)} transactions.")
                db_tagger.create_tagged_pdf(actual_pdf, coords, prefix)
            else:
                print("   > No transactions found.")

        elif bank == "BANAMEX":
            banamex_tagger.process_file(filename, prefix)

        elif bank == "BBVA":
            bbva_tagger.process_file(filename, prefix)

        elif bank == "SANTANDER":
            santander.process_file(filename, prefix)

        elif bank == "MONEX":
            monex_tagger.process_file(filename, prefix)
            
        else:
            print(f"❌ Unknown bank for {filename}")

    except Exception as e:
        print(f"❌ Error processing {filename}: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("=========================================")
    print("   BANK STATEMENT TAGGER (ALL-IN-ONE)    ")
    print("=========================================")
    
    # 1. Find PDFs
    pdfs = [f for f in glob.glob("*.pdf") if "_TAGGED" not in f and "_OCR" not in f]
    
    if not pdfs:
        print("❌ No PDF files found in the current directory.")
        input("Press Enter to exit...")
        sys.exit()
    
    # 2. List and Select
    print("\nAvailable Files:")
    for idx, f in enumerate(pdfs):
        bank, currency = detector.detect_bank_and_currency(f)
        bank_str = f"[{bank}-{currency}]" if bank != "UNK" else "[?]"
        print(f"  {idx + 1}. {f}  {bank_str}")
        
    selection = input("\nEnter file number(s) to process (comma separated, or 'all'): ").strip()
    
    selected_indices = []
    if selection.lower() == 'all':
        selected_indices = range(len(pdfs))
    else:
        parts = selection.split(',')
        for p in parts:
            if p.strip().isdigit():
                val = int(p.strip()) - 1
                if 0 <= val < len(pdfs):
                    selected_indices.append(val)
    
    if not selected_indices:
        print("No valid selection.")
        return

    # 3. Process
    for idx in selected_indices:
        filename = pdfs[idx]
        bank, currency = detector.detect_bank_and_currency(filename)
        
        if bank == "UNK":
            print(f"\nCould not detect bank for '{filename}'.")
            print("1. HSBC\n2. Banamex\n3. BBVA\n4. Santander\n5. Monex\n6. Deutsche Bank")
            choice = input("Select Bank Number: ").strip()
            mapping = {"1": "HSBC", "2": "BANAMEX", "3": "BBVA", "4": "SANTANDER", "5": "MONEX", "6": "DB"}
            bank = mapping.get(choice)
        
        if bank:
            # Suggest prefix based on detection
            default_prefix = f"{bank}_{currency}_TAG"
            prefix = input(f"\nEnter Prefix for {filename} (Default: {default_prefix}): ").strip()
            if not prefix: prefix = default_prefix
            
            process_file(filename, bank, prefix)
        else:
            print("Skipping file (No bank selected).")

    print("\n✅ All tasks completed.")
    input("Press Enter to close...")

if __name__ == "__main__":
    main()
