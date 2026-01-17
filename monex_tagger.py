import fitz  # PyMuPDF
import re
import os
import sys
import ocr_utils

def get_lines_from_page(page):
    """
    Groups words into lines based on Y coordinates (tolerance 10px).
    Used to iterate through the document structure.
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

def process_monex_page(page, lines, prefix, counter):
    # Get all words raw to perform loose zone search
    all_words = page.get_text("words")
    
    for y in sorted(lines.keys()):
        line_words = sorted(lines[y], key=lambda x: x[0])
        line_text = " ".join([w[4] for w in line_words])
        
        # 1. Find the 8-digit Reference Number (Primary Anchor)
        ref_match = re.search(r'\b\d{8}\b', line_text)
        if not ref_match: continue
        
        ref_val = ref_match.group(0)
        
        # Get exact coordinates of the reference word object
        ref_word_obj = None
        for w in line_words:
            if w[4] == ref_val:
                ref_word_obj = w
                break
        
        if not ref_word_obj: continue
        
        ref_x_end = ref_word_obj[2] # x1 (Right edge of ref)
        ref_y_mid = (ref_word_obj[1] + ref_word_obj[3]) / 2 # mid Y
        
        # 2. Zone Search Strategy
        # Search for words that are:
        # a) To the right of the reference
        # b) Within +/- 20 pixels vertically of the reference center
        
        words_in_zone = []
        for w in all_words:
            w_y_mid = (w[1] + w[3]) / 2
            # Check Vertical proximity (+/- 20px)
            if abs(w_y_mid - ref_y_mid) < 20:
                # Check Horizontal position (Must be to the right)
                if w[0] > ref_x_end:
                    words_in_zone.append(w)
        
        # Sort left-to-right to maintain logical reading order (Amount -> 0.00 Balance)
        words_in_zone = sorted(words_in_zone, key=lambda x: x[0])
        
        numbers_found = []
        for w in words_in_zone:
            txt = w[4].replace(',', '')
            try:
                val = float(txt)
                numbers_found.append((val, w))
            except:
                pass
        
        target_zero_rect = None
        
        # 3. Apply Zero-Balance Logic
        # We look for a positive amount followed immediately by 0.00, or preceded by 0.00
        for i in range(len(numbers_found)):
            val, w = numbers_found[i]
            if val > 0.00: 
                # Check Next (Standard Monex format: Amount ... 0.00)
                if i + 1 < len(numbers_found) and numbers_found[i+1][0] == 0.0:
                    target_zero_rect = fitz.Rect(numbers_found[i+1][1][:4])
                    break 
                # Check Previous (Rare Monex format: 0.00 ... Amount)
                if i - 1 >= 0 and numbers_found[i-1][0] == 0.0:
                    target_zero_rect = fitz.Rect(numbers_found[i-1][1][:4])
                    break 

        if target_zero_rect:
            key = f"{prefix}_{counter}"
            
            # Cover the 0.00 with a white box (existing logic)
            cover_rect = fitz.Rect(target_zero_rect.x0 - 5, target_zero_rect.y0 - 2, target_zero_rect.x1 + 5, target_zero_rect.y1 + 2)
            page.draw_rect(cover_rect, color=(1, 1, 1), fill=(1, 1, 1))
            
            # Place tag to the left of where the 0.00 was
            text_x = target_zero_rect.x0 - 10 
            
            # Measure height of the Reference Number (y1 - y0)
            dynamic_fontsize = max(ref_word_obj[3] - ref_word_obj[1], 10)
            
            # DEBUG: Draw circle
            page.draw_circle((text_x, ref_word_obj[3]), 2, color=(0, 0, 1), fill=(0, 0, 1))

            # Align text vertically with the Reference Number using the calculated size
            page.insert_text((text_x, ref_word_obj[3]), key, fontsize=dynamic_fontsize, color=(1, 0, 0))
            counter += 1
            
    return counter

def process_file(filename, prefix):
    try:
        # OCR Check
        if not ocr_utils.has_readable_text(filename):
             ocr_result = ocr_utils.force_ocr(filename)
             if ocr_result:
                 filename = ocr_result

        doc = fitz.open(filename)
        print(f"🏦 Processing MONEX File: {filename}")
        
        counter = 1
        for page in doc:
            lines = get_lines_from_page(page)
            if lines:
                counter = process_monex_page(page, lines, prefix, counter)
                
        output = filename.replace(".pdf", "_MONEX_TAGGED.pdf")
        doc.save(output)
        print(f"✅ Done! {counter - 1} movements tagged.")
        print(f"📁 Saved as: {output}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("--- MONEX AUTOMATOR ---")
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
    prefix = input("Enter Prefix (e.g. MNX_EUR): ").strip()
    
    if prefix:
        process_file(target_pdf, prefix)
    else:
        print("Prefix required.")