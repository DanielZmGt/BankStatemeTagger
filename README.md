# Universal Bank Statement Tagger

A powerful, standalone application to tag and organize bank statements from multiple banks using OCR and smart text analysis. Now featuring a user-friendly GUI and automatic currency detection.

## Supported Banks
- **HSBC** (Mexico/Global)
- **Citibanamex**
- **BBVA**
- **Santander**
- **Monex**
- **Deutsche Bank** (Beta)

## Key Features
- **Graphic User Interface (GUI)**: Easy-to-use interface to select files, configure settings, and view logs (`gui.py`).
- **Smart Auto-Detection**: Automatically identifies the **Bank** and **Currency** (MXN, USD, EUR) using file content analysis and heuristics.
- **Customizable Tags**: Configure your output filename pattern (e.g., `[BANK]_[CURR]_TAG` -> `HSBC_USD_TAG`).
- **OCR Engine Included**: Bundled Tesseract-OCR and Poppler binaries handle scanned documents and non-selectable text automatically.
- **Robust Parsing**: Distinguishes between transaction amounts, balances, and extraneous text.

## Installation (Source)

1. **Prerequisites**: Python 3.8 or higher.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: This project includes necessary binaries in the `bin/` folder, so you do not need to manually install Tesseract or Poppler for standard usage.*

## Usage

### 1. Graphical Interface (Recommended)
Run the GUI for the best experience:
```bash
python gui.py
```
1. Click **Select PDF Files** to choose your statements.
2. (Optional) Customize the **Tag Prefix Pattern**. Use placeholders `[BANK]` and `[CURR]`.
3. Click **Start Tagging**.

### 2. Command Line Interface
For quick processing or scripting:
```bash
python main.py
```
Follow the on-screen prompts to select files and confirm detection.

## Building the Executable
To create a standalone `.exe` file that requires no Python installation:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Run the build command using the included spec file:
   ```bash
   pyinstaller BankStatementTagger.spec
   ```
3. The executable will be found in the `dist/BankStatementTagger` folder.

## License
[MIT](LICENSE)