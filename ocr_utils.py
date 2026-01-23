import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfWriter, PdfReader
from PIL import ImageEnhance
import os
import sys
import io
import fitz

# Configuration for bundled binaries
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle
    base_path = sys._MEIPASS
    
    # Set Tesseract path
    tesseract_cmd_path = os.path.join(base_path, 'bin', 'Tesseract-OCR', 'tesseract.exe')
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path
    
    # Set Poppler path for pdf2image
    poppler_path = os.path.join(base_path, 'bin', 'poppler')
else:
    # Running in normal Python environment
    # Check if we have local bin folder (e.g. during dev)
    local_bin_tesseract = os.path.join(os.getcwd(), 'bin', 'Tesseract-OCR', 'tesseract.exe')
    local_bin_poppler = os.path.join(os.getcwd(), 'bin', 'poppler')
    
    if os.path.exists(local_bin_tesseract):
        pytesseract.pytesseract.tesseract_cmd = local_bin_tesseract
        
    if os.path.exists(local_bin_poppler):
        poppler_path = local_bin_poppler
    else:
        poppler_path = None # Rely on PATH

def clean_image(image):
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.5)
    return image

def force_ocr(input_pdf_path):
    print(f"   > OCR: Converting '{os.path.basename(input_pdf_path)}' to searchable PDF...")
    temp_output_path = input_pdf_path.replace(".pdf", "_OCR.pdf")
    
    try:
        if poppler_path:
            images = convert_from_path(input_pdf_path, dpi=300, poppler_path=poppler_path)
        else:
            images = convert_from_path(input_pdf_path, dpi=300)

        pdf_writer = PdfWriter()

        for i, image in enumerate(images):
            # print(f"     - Processing page {i + 1}/{len(images)}")
            processed_image = clean_image(image)
            custom_config = r'--psm 6'
            
            try:
                page_pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    processed_image, 
                    extension='pdf', 
                    lang='eng+spa', 
                    config=custom_config
                )
            except pytesseract.TesseractError:
                 page_pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    processed_image, 
                    extension='pdf',
                    config=custom_config
                )
            
            pdf_page = PdfReader(io.BytesIO(page_pdf_bytes))
            pdf_writer.add_page(pdf_page.pages[0])

        with open(temp_output_path, "wb") as f:
            pdf_writer.write(f)
            
        print(f"   > OCR Success: {temp_output_path}")
        return temp_output_path
        
    except Exception as e:
        print(f"   > OCR Failed: {e}")
        return None

def has_readable_text(pdf_path, keywords=None):
    if keywords is None:
        keywords = ["FECHA", "SALDO", "MOVIMIENTO", "DATE", "BALANCE", "DEPOSITO", "RETIRO", "ABONO", "CARGO", "REFERENCIA"]
    
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        
        doc.close()
        
        if len(text.strip()) < 50: # Very little text
            return False
            
        upper_text = text.upper()
        
        # Check if any keyword is present
        match_count = 0
        for k in keywords:
            if k in upper_text:
                match_count += 1
        
        # If we find at least 1 keyword, it's likely readable
        return match_count > 0
    except:
        return False
