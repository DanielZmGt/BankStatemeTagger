import pdfplumber
import fitz  # PyMuPDF
import os
import glob
import re
import ocr_utils

def is_amount(text):
    """
    Checks if a string looks like a DB statement amount.
    Examples: '20.00', '1,234.56', '+400,000.00', '-50.00'
    Must end with a dot followed by two digits (standard PDF currency format).
    """
    # Clean up common currency symbols/markers
    clean = text.replace(' ', '').replace(',', '').replace('+', '').replace('-', '')
    try:
        # Check if it's a valid number
        float(clean)
        # Regex: Ensure it ends with .XX (e.g. .00, .56)
        # This prevents tagging page numbers or years like '2021'
        if re.search(r'\.\d{2}$', text.strip()):
            return True
        return False
    except ValueError:
        return False

def find_table_bounds(page):
    """
    Finds the vertical boundaries (Y-axis) of the transaction list.
    Top: 'Bookdate' or 'Start Balance'
    Bottom: 'Sum of', 'Close Balance', 'No. Debit TX'
    """
    words = page.extract_words()
    y_min = 0
    y_max = page.height

    # Sort words by vertical position
    words_sorted = sorted(words, key=lambda w: w['top'])
    
    for w in words_sorted:
        text = w['text'].upper()
        
        # --- HEADER DETECTION ---
        if "BOOKDATE" in text or "START BALANCE" in text:
            # The list starts below these keywords
            y_min = max(y_min, w['bottom'])
        
        # --- FOOTER DETECTION ---
        if "SUM OF" in text or "CLOSE BALANCE" in text or "NO. DEBIT" in text:
            # The list ends above these keywords
            # We want the highest (earliest) occurrence of a footer word
            if y_max == page.height: 
                y_max = w['top']
            else:
                y_max = min(y_max, w['top'])

    return y_min, y_max

def get_transaction_coordinates(pdf_path):
    print(f"   > Scanning file structure...")
    
    # OCR Check
    if not ocr_utils.has_readable_text(pdf_path):
        ocr_res = ocr_utils.force_ocr(pdf_path)
        if ocr_res:
            pdf_path = ocr_res

    tagging_data = []
    transaction_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        # ... logic ...
        for page_num, page in enumerate(pdf.pages):
            # 1. Find where the table starts and ends on this page
            y_min, y_max = find_table_bounds(page)
            
            # Fallbacks if headers aren't found (e.g., middle pages of a long statement)
            if y_min == 0: y_min = 100 
            if y_max == page.height: y_max = page.height - 100

            # 2. Extract and group text
            words = page.extract_words(keep_blank_chars=False)
            
            lines = {}
            for word in words:
                # Group words into lines (tolerance of 5 pixels)
                y_axis = round(word['top'] / 5) * 5 
                if y_axis not in lines:
                    lines[y_axis] = []
                lines[y_axis].append(word)

            sorted_y_keys = sorted(lines.keys())
            
            # 3. Process each line
            for y in sorted_y_keys:
                line_words = lines[y]
                line_words.sort(key=lambda w: w['x0']) # Sort left to right
                
                # Check bounds
                line_top = line_words[0]['top']
                if line_top < y_min or line_top > y_max:
                    continue

                # 4. Check for Amounts in the line
                amounts = [w for w in line_words if is_amount(w['text'])]
                
                target_word = None
                
                if len(amounts) >= 2:
                    # If multiple amounts, the last one is likely the Running Balance.
                    # We tag the one before it (the Transaction Amount).
                    target_word = amounts[-2]
                elif len(amounts) == 1:
                    # If only one amount, check its position.
                    # Balance usually sits at the far right (e.g., > 80% of page width).
                    w = amounts[0]
                    # Normalized X check (assuming typical A4 width ~600pts)
                    if w['x0'] < page.width * 0.82:
                        target_word = w
                    # else: likely balance, skip it.
                
                if target_word:
                    transaction_count += 1
                    
                    # 5. Calculate Tag Position
                    # Place it to the right of the amount
                    x_pos = target_word['x1'] + 10 
                    y_pos = (target_word['top'] + target_word['bottom']) / 2
                    
                    # Boundary check
                    if x_pos > page.width - 50:
                        x_pos = target_word['x0'] - 60 

                    tagging_data.append({
                        "page_index": page_num,
                        "x": x_pos,
                        "y": y_pos,
                        "count": transaction_count
                    })

    return tagging_data, pdf_path

def create_tagged_pdf(pdf_path, tagging_data, prefix):
    print(f"   > Writing {len(tagging_data)} tags to new PDF...")
    
    doc = fitz.open(pdf_path)
    
    for item in tagging_data:
        page_idx = item['page_index']
        x_pos = item['x']
        y_pos = item['y']
        count = item['count']
        tag_text = f"{prefix}_{count}"
        
        if page_idx < len(doc):
            page = doc[page_idx]
            
            # DEBUG: Draw circle
            page.draw_circle((x_pos, y_pos), 3, color=(0, 0, 1), fill=(0, 0, 1))
            
            # Red color, font size 10 (enforced min)
            page.insert_text((x_pos, y_pos + 3), tag_text, fontsize=12, color=(1, 0, 0))

    base_name = os.path.splitext(pdf_path)[0]
    output_filename = f"{base_name}_TAGGED.pdf"
    
    doc.save(output_filename)
    doc.close()
    
    return output_filename

def select_file():
    pdf_files = glob.glob("*.pdf")
    pdf_files = [f for f in pdf_files if "_TAGGED" not in f]
    
    if not pdf_files:
        print("No suitable PDF files found.")
        return None

    print("\n--- Available PDF Files ---")
    for index, filename in enumerate(pdf_files):
        print(f"{index + 1}. {filename}")
    
    while True:
        try:
            choice = int(input("\nSelect a file number: "))
            if 1 <= choice <= len(pdf_files):
                return pdf_files[choice - 1]
        except ValueError: pass

if __name__ == "__main__":
    print("--- Deutsche Bank PDF Tagger ---")
    
    selected_file = select_file()
    
    if selected_file:
        prefix_input = input(f"Enter TAG PREFIX (e.g., DB_EUR): ")
        
        try:
            coords = get_transaction_coordinates(selected_file)
            
            if coords:
                print(f"   > Found {len(coords)} transactions.")
                output_file = create_tagged_pdf(selected_file, coords, prefix_input)
                print(f"\nSuccess! Created tagged file: {output_file}")
            else:
                print("\nNo transactions found.")
            
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()