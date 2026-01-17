# Universal Bank Statement Tagger

A standalone application to tag bank statements from multiple mxn banks using OCR and smart text analysis.

## Supported Banks
- HSBC
- Banamex
- BBVA
- Santander
- Monex
- Deutsche Bank (beta)

## Features
- **Auto-Detection**: Automatically identifies the bank based on filename.
- **OCR Fallback**: Handles scanned documents and Mojibake (corrupted text) automatically.
- **Smart Tagging**: Identifies transaction amounts vs balances.

## Installation
1. Install Python 3.8+.
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Install **Poppler** (for PDF conversion) and **Tesseract-OCR**.

## Usage
1. Place your PDF bank statements in the same folder as the script.
2. Run the application:
   ```bash
   python main.py
   ```
3. Select the files you want to process.
