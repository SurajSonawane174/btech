# AI Engine — Engineering Comment Extraction & Classification

Part of the **Engineering Comment Extraction & Classification Platform**.  
This module processes engineering drawing PDFs, extracts reviewer comments,
classifies them, captures screenshots, and outputs structured JSON + CSV.

---

## Setup

### 1. Prerequisites

**Python 3.9+** is required.

**Tesseract OCR** must be installed on your system (required for scanned PDFs):

- **Windows:**  
  Download installer from https://github.com/UB-Mannheim/tesseract/wiki  
  Default install path: `C:\Program Files\Tesseract-OCR\tesseract.exe`  
  Add it to your system PATH, or set in code:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```

- **Ubuntu/Debian:**
  ```bash
  sudo apt install tesseract-ocr
  ```

- **macOS:**
  ```bash
  brew install tesseract
  ```

### 2. Python Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. API Key Setup

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your Gemini API key
# Get your key from: https://aistudio.google.com/app/apikey
```

Your `.env` should look like:
```
GEMINI_API_KEY=AIzaSy...your_actual_key...
```

Then load it before running (Windows PowerShell):
```powershell
$env:GEMINI_API_KEY = "AIzaSy...your_actual_key..."
```

Or on Mac/Linux:
```bash
export GEMINI_API_KEY="AIzaSy...your_actual_key..."
```

Or use python-dotenv (optional):
```bash
pip install python-dotenv
```
And add to the top of `doc_process.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Usage

### Process a single PDF
```bash
python doc_process.py --input path/to/drawing.pdf
```

### Process a folder of PDFs
```bash
python doc_process.py --input path/to/drawings/
```

### Process with glob pattern
```bash
python doc_process.py --input "drawings/*.pdf"
```

### Specify number of parallel workers
```bash
python doc_process.py --input drawings/ --workers 4
```

### Use a custom config file
```bash
python doc_process.py --input drawings/ --config my_config.yaml
```

---

## Expected Filename Format

The engine parses metadata from the PDF filename. Expected format:

```
{PROJECT}_{ANYTHING}_{DRAWING_NUMBER}_{REVISION}.pdf
```

Examples:
- `PRAJ_P101_DWG-001_R2.pdf`  → Project: PRAJ, Drawing: DWG-001, Revision: R2
- `ACME_Layout_A-2301_R0.pdf` → Project: ACME, Drawing: A-2301, Revision: R0

If your filename format is different, update `extract_metadata()` in `doc_process.py`.

---

## Output Structure

```
output/
└── {pdf_name}/
    ├── comments.json        ← Full structured data (all fields)
    ├── final_output.csv     ← Full detail CSV (Excel-compatible)
    ├── summary.csv          ← Category counts and percentages
    └── images/
        └── {uid}.png        ← Screenshot per comment
```

### Comment ID Format
```
{PROJECT}-{DRAWING}-{PAGE:03d}-{ROW:03d}-{SEQ:03d}
```
Example: `PRAJ-DWG001-001-045-003`

---

## Configuration (config.yaml)

Key settings you may want to adjust:

| Setting | Default | Description |
|---|---|---|
| `ocr.enabled` | `true` | Enable/disable OCR for scanned pages |
| `ocr.dpi` | `300` | Render quality for OCR |
| `classification.similarity_threshold` | `90` | When to flag as "repeated" |
| `classification.gemini_model` | `gemini-1.5-flash` | Gemini model to use |
| `screenshot.margin` | `1.15` | Context padding around annotation |
| `scanned_text_threshold` | `50` | Chars below which a page is treated as scanned |

---

## Troubleshooting

**"GEMINI_API_KEY environment variable is not set"**  
→ Make sure you set the env variable before running. See Setup step 3.

**"Config file not found: config.yaml"**  
→ Make sure `config.yaml` is in the same folder as `doc_process.py`.

**"TesseractNotFoundError"**  
→ Tesseract is not installed or not in PATH. See Setup step 1.

**No comments extracted from a PDF**  
→ Check if the PDF has embedded annotations (open in Adobe Acrobat → View → Comments).  
→ If annotations are absent, the PDF may need OCR — ensure `ocr.enabled: true`.

**Gemini returns unexpected responses**  
→ The engine automatically falls back to rule-based classification. No action needed.
