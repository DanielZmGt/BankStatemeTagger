import fitz  # PyMuPDF
import re
import os
import sys
import glob

def get_lines_from_page(page):
    """
    Groups words into lines based on Y coordinates (tolerance 5px).
    This helps reconstruct rows in the PDF.
    """
    words = page.get_text("words")
    lines = {}
    for w in words:
        # Round Y coordinate to group words on the same line
        y_coord = round(w[1])
        found = False
        for existing_y in lines:
            if abs(existing_y - y_coord) < 5: 
                lines[existing_y].append(w)
                found = True
                break
        if not found:
            lines[y_coord] = [w]
    return lines

def extract_expected_totals(doc):
    """
    Scans the document (starting from the end) to find the summary table:
    'TOTAL MOVIMIENTOS CARGOS' and 'TOTAL MOVIMIENTOS ABONOS'
    Returns the sum of both.
    """
    cargos = 0
    abonos = 0
    
    # BBVA summaries are usually on the last page or second to last
    # We scan backwards to find it faster
    for i in range(len(doc)-1, -1, -1):
        page = doc[i]
        # Get plain text to search for keywords
        text = page.get_text("text").upper()
        
        # Normalize whitespace (replace newlines with spaces) for easier regex
        clean_text = re.sub(r'\s+', ' ', text)
        
        if "TOTAL MOVIMIENTOS" in clean_text:
            print(f"   > Found Summary on Page {i+1}")
            
            # Regex to find the numbers associated with the keywords
            # Looks for "TOTAL MOVIMIENTOS CARGOS" followed optionally by spaces/punctuation then digits
            c_match = re.search(r'TOTAL MOVIMIENTOS CARGOS\s*[\D]*\s*(\d+)', clean_text)
            a_match = re.search(r'TOTAL MOVIMIENTOS ABONOS\s*[\D]*\s*(\d+)', clean_text)
            
            if c_match: 
                cargos = int(c_match.group(1))
                print(f"     - Cargos found: {cargos}")
            
            if a_match: 
                abonos = int(a_match.group(1))
                print(f"     - Abonos found: {abonos}")
            
            # If we found data, stop scanning
            if cargos > 0 or abonos > 0:
                break
                
    return cargos + abonos

def process_bbva_page(page, lines, prefix, counter):
    """
    Tags lines that start with a Date (e.g., 02/OCT).
    """
    # Regex for BBVA dates: 2 digits, slash, 3 uppercase letters (e.g., 02/OCT)
    date_pattern = re.compile(r'\d{2}/[A-Z]{3}', re.IGNORECASE)
    
    # Get page width to place tags on the right side
    page_width = page.rect.width
    
    # Sort Y coordinates to read top-to-bottom
    for y in sorted(lines.keys()):
        # Sort words in line left-to-right
        line_words = sorted(lines[y], key=lambda x: x[0])
        
        # Reconstruct the text line
        line_text = " ".join([w[4] for w in line_words]).upper()
        
        # --- FILTERS ---
        
        # 1. Skip Header Lines
        if "FECHA" in line_text and "OPER" in line_text: 
            continue
            
        # 2. Check first word for Date Format
        # BBVA transactions always start with the date
        first_word_text = line_words[0][4].upper()
        
        # Clean up potential OCR noise around the date
        clean_first_word = first_word_text.replace('.', '').replace(',', '')
        
        if not date_pattern.match(clean_first_word):
            continue
            
        # --- TAGGING ---
        
        key = f"{prefix}_{counter}"
        
        # Use the height of the date text to determine tag font size
        # w[1] is top-y, w[3] is bottom-y
        date_word = line_words[0]
        text_height = date_word[3] - date_word[1]
        
        # Calculate X position (RIGHT SIDE)
        # fitz.get_text_length estimates width of our tag string
        tag_width = fitz.get_text_length(key, fontname="helv", fontsize=text_height)
        
        # Place it at the Page Width minus the tag width minus a 40px margin
        # This aligns everything neatly on the right side of the sheet
        x_pos = page_width - tag_width - 40
            
        # Vertical alignment (slightly adjusted for baseline)
        y_pos = date_word[3] - (text_height * 0.15)
        
        # Insert Tag
        page.insert_text((x_pos, y_pos), key, fontsize=text_height, color=(1, 0, 0))
        
        counter += 1
            
    return counter

def process_file(filename, prefix):
    try:
        doc = fitz.open(filename)
        print(f"\n🏦 Processing BBVA File: {filename}")
        
        # 1. Get Expected Count from Summary
        expected_total = extract_expected_totals(doc)
        if expected_total == 0:
            print("   ⚠️ WARNING: Could not find 'Total de Movimientos' summary table.")
        
        # 2. Tag Pages
        counter = 1
        start_processing = False
        
        for page_num, page in enumerate(doc):
            lines = get_lines_from_page(page)
            page_text = page.get_text("text").upper()
            
            # Simple Logic: Only start tagging AFTER we see the "Detalle de Movimientos" header
            # This prevents tagging dates in the header summary or ads
            if "DETALLE DE MOVIMIENTOS" in page_text:
                start_processing = True
                
            if start_processing and lines:
                counter = process_bbva_page(page, lines, prefix, counter)
                
        actual_tagged = counter - 1
        
        # 3. Validation Report
        print(f"   ----------------------------------------")
        print(f"   Expected (from PDF): {expected_total}")
        print(f"   Actual Tags Created: {actual_tagged}")
        
        if expected_total > 0:
            if expected_total == actual_tagged:
                print(f"   ✅ SUCCESS: Counts match perfectly!")
            else:
                diff = abs(expected_total - actual_tagged)
                print(f"   ❌ MISMATCH: Difference of {diff} movements.")
                print(f"      (Check if some dates were missed or headers tagged by mistake)")
        
        # 4. Save
        output = filename.replace(".pdf", "_BBVA_TAGGED.pdf")
        doc.save(output)
        print(f"   📁 Saved as: {output}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("--- BBVA STATEMENT TAGGER (Standalone Test) ---")
    
    # Find all PDFs in current folder that aren't already tagged
    pdfs = [f for f in glob.glob("*.pdf") if "_TAGGED" not in f and "_HIGH_CONTRAST" not in f]
    
    if not pdfs:
        print("❌ No suitable PDF files found in this folder.")
        input("Press Enter to exit...")
        sys.exit()

    # List files
    for idx, f in enumerate(pdfs):
        print(f"  [{idx + 1}] {f}")
        
    # Select File
    sel = input("\nSelect File (Number): ").strip()
    if not (sel.isdigit() and 1 <= int(sel) <= len(pdfs)):
        sys.exit("Invalid selection.")
        
    target_pdf = pdfs[int(sel) - 1]
    
    # Enter Prefix
    prefix = input("Enter Tag Prefix (e.g. BBVA_OCT): ").strip()
    if not prefix: prefix = "BBVA"
    
    process_file(target_pdf, prefix)
    input("\nPress Enter to close...")