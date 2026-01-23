import fitz
import re
import os
import ocr_utils

BANKS = {
    "HSBC": ["HSBC"],
    "BANAMEX": ["BANAMEX", "CITIBANAMEX"],
    "BBVA": ["BBVA", "BANCOMER"],
    "SANTANDER": ["SANTANDER"],
    "MONEX": ["MONEX"],
    "DB": ["DEUTSCHE BANK", "DEUTSCHE"],
}

# Currency regex patterns
CURRENCIES = {
    "MXN": [r"\bMXN\b", r"\bPESOS\b", r"\bM\.N\.\b", r"\bMONEDA NACIONAL\b"],
    "USD": [r"\bUSD\b", r"\bDOLLARS\b", r"\bDOLARES\b", r"\bUS DOLLAR\b"],
    "EUR": [r"\bEUR\b", r"\bEUROS\b"],
}

def get_text_head(file_path, max_pages=2):
    """Extracts text from the first few pages for detection."""
    text = ""
    try:
        # Try native PDF text first
        doc = fitz.open(file_path)
        for i, page in enumerate(doc):
            if i >= max_pages: break
            text += page.get_text() + "\n"
        doc.close()
        
        # If text is too sparse, it might be an image scan.
        if len(text.strip()) < 50:
            print(f"   > Text too sparse in {os.path.basename(file_path)}, attempting OCR for detection...")
            # We don't want to force a full OCR convert just for detection if we can avoid it,
            # but if we must, we might just look at the filename or punt.
            # For now, let's assume we rely on what we have or filename fallback.
            pass
            
    except Exception as e:
        print(f"   > Error reading {file_path}: {e}")
        return ""
        
    return text.upper()

def detect_bank_and_currency(file_path):
    """
    Returns (bank_code, currency_code)
    e.g. ("HSBC", "MXN")
    """
    filename = os.path.basename(file_path).upper()
    
    # 1. Detect Bank (Filename has high priority for Bank)
    detected_bank = "UNK"
    for code, keywords in BANKS.items():
        for k in keywords:
            if k in filename:
                detected_bank = code
                break
        if detected_bank != "UNK": break
    
    # 2. Extract content for deeper analysis (Currency needs content usually)
    content = get_text_head(file_path)
    
    # Refine Bank if unknown from filename
    if detected_bank == "UNK":
        for code, keywords in BANKS.items():
            for k in keywords:
                if k in content:
                    detected_bank = code
                    break
            if detected_bank != "UNK": break

    # 3. Detect Currency
    detected_curr = "MXN" # Default
    
    scores = {"MXN": 0, "USD": 0, "EUR": 0}
    
    for code, patterns in CURRENCIES.items():
        for p in patterns:
            matches = re.findall(p, content)
            scores[code] += len(matches)
            
    # Simple heuristic: if USD > 0 and USD >= MXN, call it USD.
    # Mexican statements often mention "Pesos" in fine print even if USD account.
    # So we need strong signal for USD/EUR.
    
    if scores["EUR"] > 0 and scores["EUR"] >= scores["USD"] and scores["EUR"] >= scores["MXN"]:
        detected_curr = "EUR"
    elif scores["USD"] > 0 and scores["USD"] >= scores["MXN"]:
        detected_curr = "USD"
    elif scores["MXN"] > 0:
        detected_curr = "MXN"
    
    # If no currency detected in text, maybe filename has it?
    if scores["MXN"] == 0 and scores["USD"] == 0 and scores["EUR"] == 0:
        if "USD" in filename or "DOLAR" in filename: detected_curr = "USD"
        elif "EUR" in filename or "EURO" in filename: detected_curr = "EUR"
    
    return detected_bank, detected_curr
