Bank Statement Tagger - Standalone Version
==========================================

This application automatically tags and organizes your bank statement PDFs.

Features:
- Supports HSBC, Banamex, BBVA, Santander, Monex, and Deutsche Bank.
- Detects Currency (MXN, USD, EUR) automatically.
- Includes OCR engine to read scanned documents.

How to use:
1. Double-click "BankStatementTagger.exe" to launch the application.
2. Click "Select PDF Files" and choose your bank statements.
3. (Optional) In the "Tag Prefix Pattern" box, you can customize how the output files are named.
   - Default: [BANK]_[CURR]_TAG
   - Example Result: HSBC_MXN_TAG_MyStatement.pdf
4. Click "Start Tagging".
5. The tagged files will be created in the same folder as the originals.

Requirements:
- Windows 10 or 11.
- No external software installation required (Tesseract OCR and Poppler are bundled).

Troubleshooting:
- If the app doesn't open, try running it as Administrator.
- If a bank is not detected correctly, the file will be skipped or tagged as "UNK" (Unknown). You can rename the file to include the bank name (e.g., "HSBC_Statement.pdf") to help the detector.

Enjoy!