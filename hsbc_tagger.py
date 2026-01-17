import pdfplumber
import fitz  # PyMuPDF
import os
import glob
import re
import sys
import traceback
import ocr_utils

def is_valid_day(val):
    if not val: return False
    clean = str(val).strip().replace('.', '').replace(',', '').replace(' ', '').upper().replace('O', '0')
    match = re.match(r'^(\d{1,2})', clean)
    if match: clean = match.group(1)
    if '/' in clean: clean = clean.split('/')[0]
    if clean.isdigit() and 1 <= int(clean) <= 31: return True
    return False

def get_amounts(line_words):
    amounts = []
    for w in line_words:
        text = w['text'].replace('$', '').replace(',', '').strip()
        if '.' in text:
            try:
                float(text)
                amounts.append(w)
            except ValueError: continue
    return amounts

def contains_currency(line_words):
    return len(get_amounts(line_words)) > 0

def is_summary_line(text):
    if not text: return False
    keywords = ["SALDO PROMEDIO", "SALDO FINAL", "TOTAL", "RESUMEN", "INFORMATIVO", "PAGINA", "HOJA", "DIAS TRANSCURRIDOS", "SALDO INICIAL", "DEPOSITOS", "RETIROS"]
    upper = text.upper()
    for k in keywords:
        if k in upper: return True
    return False

def find_header_y(page):
    words = page.extract_words()
    lines = {}
    for w in words:
        y = round(w['top'] / 5) * 5
        if y not in lines: lines[y] = []
        lines[y].append(w)
    for y in sorted(lines.keys()):
        line_text = " ".join([w['text'] for w in lines[y]]).upper()
        if "DETALLE" in line_text and "MOVIMIENTOS" in line_text:
            return max(w['bottom'] for w in lines[y])
    return 0

def get_transaction_coordinates(pdf_path):
    print(f"   > Scanning file structure...")
    
    if not ocr_utils.has_readable_text(pdf_path):
        print("   > Text not readable. Attempting OCR...")
        ocr_pdf = ocr_utils.force_ocr(pdf_path)
        if ocr_pdf: pdf_path = ocr_pdf 

    tagging_data = []
    transaction_count = 0
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words(keep_blank_chars=False)
            width = page.width
            
            # Define exact column percentages for HSBC OCR
            # Based on 2622px width analysis
            # W_Zone: 50% - 68% (Target ~1600)
            # D_Zone: 68% - 82% (Target ~1940)
            # Balance: > 82% (Ignored)
            
            w_col_x = width * 0.61  # ~1600
            d_col_x = width * 0.74  # ~1940
            split_pct = 0.67        # ~1750
            
            min_y_threshold = 0
            if page_num == 0:
                header_bottom = find_header_y(page)
                if header_bottom > 0: min_y_threshold = header_bottom - 10
            
            # --- CLUSTERING (Fixes split lines) ---
            lines = {}
            for w in words:
                y_mid = (w['top'] + w['bottom']) / 2
                found_y = None
                for existing_y in lines.keys():
                    if abs(existing_y - y_mid) < 10: 
                        found_y = existing_y
                        break
                if found_y: lines[found_y].append(w)
                else: lines[y_mid] = [w]
            # --------------------------------------

            sorted_y_keys = sorted(lines.keys())
            
            for y in sorted_y_keys:
                line_words = lines[y]
                line_words.sort(key=lambda w: w['x0'])
                if not line_words: continue
                
                first_word = line_words[0]
                if page_num == 0 and first_word['top'] < min_y_threshold: continue

                full_line_text = " ".join([w['text'] for w in line_words]).upper()
                if is_summary_line(full_line_text): continue

                amounts = get_amounts(line_words)
                
                # STRICT FILTER: Ignore Balance Column (> 82%)
                # Also ignore anything too far left to be a transaction amount (< 50%)
                valid_amounts = [a for a in amounts if (width * 0.50) < a['x0'] < (width * 0.82)]
                
                target_word = None
                if valid_amounts: target_word = valid_amounts[-1]
                
                if target_word:
                    # Valid Start Check
                    is_valid_start = is_valid_day(first_word['text']) or first_word['x0'] < (width * 0.20)
                    
                    if is_valid_start and "SALDO" not in full_line_text and "TOTAL" not in full_line_text:
                        transaction_count += 1
                        
                        amount_x = target_word['x0']
                        x_pct = amount_x / width
                        
                        if x_pct < split_pct: 
                            # It is a Withdrawal (Left)
                            # Place Tag in Deposit Column (Right)
                            final_x = d_col_x
                            align_mode = "left" 
                        else:
                            # It is a Deposit (Right)
                            # Place Tag in Withdrawal Column (Left)
                            final_x = w_col_x
                            align_mode = "right"
                        
                        word_height = target_word['bottom'] - target_word['top']
                        y_center = target_word['top'] + (word_height / 2)
                        
                        tagging_data.append({
                            "page_index": page_num,
                            "y": y_center,
                            "x": final_x, 
                            "height": word_height, 
                            "count": transaction_count,
                            "align": align_mode
                        })
    
    return tagging_data, pdf_path

def create_tagged_pdf(pdf_path, tagging_data, prefix):
    print(f"   > Writing {len(tagging_data)} tags to new PDF...")
    doc = fitz.open(pdf_path)
    for item in tagging_data:
        page_idx = item['page_index']
        y_pos = item['y']
        x_pos = item['x']
        font_size = item['height'] 
        count = item['count']
        align = item.get('align', 'center')
        tag_text = f"{prefix}_{count}"
        
        if page_idx < len(doc):
            page = doc[page_idx]
            safe_fs = max(font_size, 10)
            text_width = len(tag_text) * (safe_fs * 0.5) 
            
            # Adjust drawing X based on alignment
            # Left: draw starting at x
            # Right: draw ending at x
            if align == "left": final_x = x_pos 
            elif align == "right": final_x = x_pos - text_width
            else: final_x = x_pos - (text_width / 2)
            
            # Visual Debugging
            page.draw_circle((x_pos, y_pos), 3, color=(0, 0, 1), fill=(0, 0, 1))
            page.insert_text((final_x, y_pos + (safe_fs/3)), tag_text, fontsize=safe_fs, color=(1, 0, 0))

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
            if 1 <= choice <= len(pdf_files): return pdf_files[choice - 1]
        except ValueError: pass

if __name__ == "__main__":
    print("--- HSBC PDF Tagger (Searchable + Dynamic Font) ---")
    selected_file = select_file()
    if selected_file:
        prefix_input = input(f"Enter TAG PREFIX (e.g., HSBC_MXN): ")
        try:
            coords, pdf = get_transaction_coordinates(selected_file)
            if coords:
                print(f"   > Found {len(coords)} transactions.")
                output_file = create_tagged_pdf(pdf, coords, prefix_input)
                print(f"\nSuccess! Created tagged file: {output_file}")
            else:
                print("\nNo transactions found.")
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
