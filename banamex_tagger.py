import fitz  # PyMuPDF
import re
import os
import sys

# --- CONFIGURATION ---
BANAMEX_SKIP_KEYWORDS = [
    "RESUMEN", "PERIODO", "SALDO", "TOTAL", "INVERSION", 
    "DEPÓSITOS", "RETIROS", "HOJA", "PÁGINA", "PAGINA", 
    "ANTERIOR", "PROMEDIO", "DÍAS", "DIAS", "CORTE",
    "CLABE", "CUENTA", "CHEQUES", "INICIAL", "FINAL"
]

def has_money(text):
    # Matches 1,000.00 or 500.00 or 0.00
    return re.search(r'\d{1,3}(?:[,\.\s]\d{3})*[,\.\s]\d{2}', text)

def get_lines_from_page(page):
    """
    Groups words into lines based on Y coordinates (tolerance 10px).
    """
    words = page.get_text("words")
    lines = {}
    for w in words:
        y_coord = round(w[1])
        found = False
        for existing_y in lines:
            if abs(existing_y - y_coord) < 10: 
                lines[existing_y].append(w)
                found = True
                break
        if not found:
            lines[y_coord] = [w]
    return lines

def process_banamex_page(page, lines, prefix, counter):
    page_width = page.rect.width

    # 1. Geometric Filter: Find "DETALLE DE OPERACIONES"
    start_tagging_y = 0
    for y in sorted(lines.keys()):
        line_text_check = " ".join([w[4] for w in lines[y]]).upper()
        if "DETALLE" in line_text_check and "OPERACIONES" in line_text_check:
            start_tagging_y = y
            break

    for y in sorted(lines.keys()):
        # Skip lines visually above the "DETALLE DE OPERACIONES" header
        if y <= start_tagging_y and start_tagging_y != 0:
            continue

        line_words = sorted(lines[y], key=lambda x: x[0])
        # Join with space to ensure regex works
        line_text = " ".join([w[4] for w in line_words]) 
        upper_text = line_text.upper()
        
        # 2. Keyword Filter
        if any(k in upper_text for k in BANAMEX_SKIP_KEYWORDS): 
            continue
        
        # 3. Date Filter (Matches "05 ENE", "12/DIC", etc.)
        if not re.search(r'\d{2}[\s/.-]+[A-Za-z]{3}', line_text): 
            continue
            
        # 4. Money Filter
        if not has_money(line_text): 
            continue
        
        # If we passed all checks, it's a transaction
        key = f"{prefix}_{counter}"
        
        # Find the specific word object that contains the money
        # We need this object to measure its height and width
        money_word = None
        for w in line_words:
            if has_money(w[4]):
                money_word = w
                break
        
        if money_word:
            # --- DYNAMIC SIZE CALCULATION ---
            # Measure height of the money text (y1 - y0)
            # This ensures the tag is the EXACT same size as the document numbers
            text_height = money_word[3] - money_word[1]
            
            # Use this height as the font size
            dynamic_font_size = text_height
            
            # --- DYNAMIC WIDTH CALCULATION ---
            # Calculate how wide the tag text will be at this specific font size
            # fitz.get_text_length calculates string width for the default font (Helvetica)
            tag_width_px = fitz.get_text_length(key, fontname="helv", fontsize=dynamic_font_size)
            
            # --- POSITIONING LOGIC ---
            # money_word tuple: (x0, y0, x1, y1, "text", ...)
            money_x0 = money_word[0] # Left edge of money
            money_x1 = money_word[2] # Right edge of money
            
            padding = 10 # Space between tag and number
            
            # If money is on the right side of the page (>70%)
            if money_x0 > (page_width * 0.7):
                # Place LEFT of the money
                # math: (Left edge of money) - (Width of tag) - (Padding)
                target_x = money_x0 - tag_width_px - padding
            else:
                # Place RIGHT of the money
                # math: (Right edge of money) + (Padding)
                target_x = money_x1 + padding
            
            # Align Y with the text baseline (bottom of the money word)
            # PyMuPDF inserts text starting from the baseline, so we use y1 roughly
            target_y = money_word[3] - (dynamic_font_size * 0.15) # Small adjust for baseline
            
            # Insert the text
            page.insert_text((target_x, target_y), key, fontsize=dynamic_font_size, color=(1, 0, 0))
            counter += 1
            
    return counter

def process_file(filename, prefix):
    try:
        doc = fitz.open(filename)
        print(f"🏦 Processing BANAMEX File: {filename}")
        
        counter = 1
        for page in doc:
            lines = get_lines_from_page(page)
            if lines:
                counter = process_banamex_page(page, lines, prefix, counter)
                
        output = filename.replace(".pdf", "_BANAMEX_TAGGED.pdf")
        doc.save(output)
        print(f"✅ Done! {counter - 1} movements tagged.")
        print(f"📁 Saved as: {output}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("--- BANAMEX AUTOMATOR (Perfect Match) ---")
    pdfs = [f for f in os.listdir('.') if f.lower().endswith('.pdf') and "_TAGGED" not in f]
    
    if not pdfs:
        print("❌ No PDFs found.")
        sys.exit()

    for idx, f in enumerate(pdfs):
        print(f"  [{idx + 1}] {f}")
        
    sel = input("\nSelect File (Number): ").strip()
    if not (sel.isdigit() and 1 <= int(sel) <= len(pdfs)):
        sys.exit("Invalid selection.")
        
    target_pdf = pdfs[int(sel) - 1]
    prefix = input("Enter Prefix (e.g. BMX_USD): ").strip()
    
    if prefix:
        process_file(target_pdf, prefix)
    else:
        print("Prefix required.")