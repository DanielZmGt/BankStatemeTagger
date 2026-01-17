import fitz  # PyMuPDF
import re
import os
import sys
import ocr_utils # Use our new utility instead of ocrmypdf

DATE_LIMIT_X = 0.18      # Límite derecho para encontrar la FECHA de la transacción
MIN_X_SEARCH = 0.60      # Inicio de búsqueda de montos (salta descripción)
MAX_X_SEARCH = 0.85      # Límite derecho (Ignora saldo final) - Ampliado un poco

# Frontera vertical entre Depósitos (Izq) y Retiros (Der)
# Ajusta esto si los depósitos se detectan como retiros
SPLIT_X = 0.76            

# Posiciones visuales donde se estampará la etiqueta roja
TAG_POS_DEPOSITO = 0.64 
TAG_POS_RETIRO   = 0.76   

def check_if_text_pdf(filename):
    """Verifica si el PDF ya tiene texto seleccionable."""
    try:
        doc = fitz.open(filename)
        text_len = 0
        for page in doc:
            text_len += len(page.get_text())
            if text_len > 500: # Umbral aumentado para evitar falsos positivos por headers
                doc.close()
                return True
        doc.close()
        return False
    except Exception as e:
        print(f"Error leyendo PDF: {e}")
        return False

def run_ocr(input_pdf):
    if not OCR_AVAILABLE:
        return input_pdf
        
    output = input_pdf.replace(".pdf", "_OCR.pdf")
    print(f"⚙️  Aplicando OCR a '{input_pdf}' (esto puede tardar)...")
    try:
        # force_ocr=True asegura que procese incluso si hay algo de texto basura
        ocrmypdf.ocr(input_pdf, output, language='spa', skip_text=True, progress_bar=False)
        return output
    except Exception as e:
        print(f"⚠️  Fallo OCR: {e}. Se usará el archivo original.")
        return input_pdf

def parse_amount(text):
    """
    Parsea montos financieros.
    CORRECCIÓN: Se eliminó el filtro que borraba montos entre 2000 y 2035.
    """
    try:
        # Limpieza básica: eliminar caracteres que no sean dígitos, puntos o comas
        clean_initial = re.sub(r'[^\d.,]', '', text)
        
        # Debe tener al menos un punto o coma decimal/miles
        if '.' not in clean_initial and ',' not in clean_initial:
            return None
            
        # Si es muy largo y no tiene separadores, probablemente es un código de referencia
        if len(clean_initial) > 9 and ',' not in clean_initial and '.' not in clean_initial:
            return None

        # Normalizar a float (asumiendo formato 1,234.56 o 1.234,56)
        # Santander México usa 1,234.56
        clean_val = clean_initial.replace(',', '') 
        val = float(clean_val)
        
        if val == 0: return None
        
        return val
    except:
        return None

def row_starts_with_date(words_in_row, page_width):
    """
    Confirma si la fila comienza con una fecha válida en el margen izquierdo.
    """
    limit_pixels = page_width * DATE_LIMIT_X
    
    # Filtrar palabras que empiezan visualmente en la zona de fecha
    candidate_words = [w for w in words_in_row if w[0] < limit_pixels]
    
    if not candidate_words:
        return False

    sorted_words = sorted(candidate_words, key=lambda w: w[0])
    
    # Unir las primeras partes para formar algo como "12 DIC" o "01/05"
    start_text = " ".join([w[4] for w in sorted_words[:3]]).upper()
    
    # Regex Mejorado:
    # Acepta: 01-ENE, 01 ENE, 12/12, 12.12, 1 DIC
    # Excluye falsos positivos que no empiecen con digito
    match = re.search(r'^\d{1,2}[\s\.\-\/]+(?:[A-Z]{3}|\d{2})', start_text)
    
    return bool(match)

def get_rows(page):
    """Agrupa palabras en renglones con tolerancia vertical."""
    words = page.get_text("words")
    rows = {}
    for w in words:
        y_mid = (w[1] + w[3]) / 2
        found_y = None
        
        # Buscar si ya existe una fila cercana (tolerancia 4px)
        for existing_y in rows.keys():
            if abs(existing_y - y_mid) < 4: 
                found_y = existing_y
                break
        
        if found_y: 
            rows[found_y].append(w)
        else: 
            rows[y_mid] = [w]
            
    return dict(sorted(rows.items()))

def process_page_strict_start(page, prefix, counter):
    page_width = page.rect.width
    
    # Coordenadas en pixeles
    x_search_start = page_width * MIN_X_SEARCH
    x_search_end   = page_width * MAX_X_SEARCH
    x_split        = page_width * SPLIT_X
    pos_dep_vis    = page_width * TAG_POS_DEPOSITO
    pos_ret_vis    = page_width * TAG_POS_RETIRO
    
    rows = get_rows(page)
    
    for y, words in rows.items():
        
        # 1. ¿Es un renglón de transacción? (Tiene fecha a la izquierda)
        if not row_starts_with_date(words, page_width):
            continue
            
        # 2. Buscar monto a la derecha
        amount_found = False
        
        for w in words:
            wx = (w[0] + w[2]) / 2 
            
            # Ignorar zona de descripción y zona de saldo final
            if wx < x_search_start or wx > x_search_end:
                continue 
            
            # Intentar parsear
            if any(c.isdigit() for c in w[4]):
                val = parse_amount(w[4])
                if val is not None:
                    
                    # 3. Clasificar (Izquierda = Deposito, Derecha = Retiro)
                    if wx < x_split:
                        # Es DEPOSITO -> Poner etiqueta en columna RETIROS
                        final_x = pos_ret_vis
                        tag_type = "DEP" 
                        color = (1, 0, 0) # Verde oscuro para depósitos
                    else:
                        # Es RETIRO -> Poner etiqueta en columna DEPOSITOS
                        final_x = pos_dep_vis
                        tag_type = "RET"
                        color = (1, 0, 0)   # Rojo para retiros
                    
                    key = f"{prefix}{counter}" # Eliminé el guion bajo para ahorrar espacio
                    
                    # Ajuste de fuente y posición
                    fs = w[3] - w[1] 
                    final_y = w[3] - (fs * 0.15)
                    
                    # Insertar etiqueta en el PDF
                    page.insert_text(
                        (final_x, final_y), 
                        key, 
                        fontsize=fs, 
                        fontname="helv", # Fuente estándar segura
                        color=color
                    )
                    
                    print(f"   [{counter}] {tag_type} | ${val:,.2f} -> Etiqueta: {key}")
                    counter += 1
                    amount_found = True
                    break # Solo tomamos el primer monto válido de la fila
        
    return counter

def process_file(filename, prefix):
    work_file = filename
    
    # Lógica de OCR usando ocr_utils
    if not ocr_utils.has_readable_text(filename):
        print(f"⚠️  Texto no detectado o ilegible. Aplicando OCR...")
        ocr_result = ocr_utils.force_ocr(filename)
        if ocr_result:
            work_file = ocr_result

    doc = None
    try:
        doc = fitz.open(work_file)
        print(f"\n🚀 Procesando: {filename}")
        
        counter = 1
        for i, page in enumerate(doc):
            # Feedback visual de progreso
            print(f"--- Pág {i+1} ---")
            counter = process_page_strict_start(page, prefix, counter)
            
        output = filename.replace(".pdf", "_TAGGED.pdf")
        doc.save(output)
        print(f"\n✅ FINALIZADO. Total Transacciones: {counter - 1}")
        print(f"📁 Archivo guardado: {output}")
        
    except Exception as e:
        print(f"❌ Error crítico procesando {filename}: {e}")
    finally:
        # IMPORTANTE: Cerrar el documento para liberar el archivo
        if doc:
            doc.close()

    # Limpieza de archivo temporal OCR
    if work_file != filename and os.path.exists(work_file):
        try:
            os.remove(work_file)
            print("🧹 Archivo temporal OCR eliminado.")
        except OSError as e:
            print(f"⚠️ No se pudo borrar el temporal (quizás sigue en uso): {e}")

if __name__ == "__main__":
    print("--- SANTANDER TAGGER V6 (FIXED) ---")
    
    # Buscar PDFs en el directorio actual
    pdfs = [f for f in os.listdir('.') if f.lower().endswith('.pdf') and "_TAGGED" not in f and "_OCR" not in f]
    
    if not pdfs:
        print("❌ No se encontraron archivos .pdf en esta carpeta.")
        input("Presiona Enter para salir...")
        sys.exit()
    
    print("\nArchivos disponibles:")
    for idx, f in enumerate(pdfs): 
        print(f"  [{idx+1}] {f}")
    
    sel = input("\nElige el número del archivo: ").strip()
    if sel.isdigit() and 0 < int(sel) <= len(pdfs):
        target_file = pdfs[int(sel)-1]
        
        # Sugerencia de prefijo inteligente (ej: ENE24)
        suggestion = "BANCO_MONEDA"
        user_prefix = input(f"Prefijo para etiquetas (Enter para '{suggestion}'): ").strip()
        prefix = user_prefix if user_prefix else suggestion
        
        process_file(target_file, prefix)
    else:
        print("Selección inválida.")