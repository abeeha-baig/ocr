# OCR Application - PDF Processing & Signin Classification

A production-ready OCR application for processing healthcare signin sheets with credential classification. Now supports **PDF input with automatic page classification**.

## ✅ Project Overview

This application processes PDF documents containing signin and dinein pages, automatically classifies them, and extracts names and credentials from signin sheets using Google Gemini AI with rule-based credential classification.

### Key Features

- **PDF Processing**: Automatic conversion of PDFs to images and page classification
- **Page Classification**: AI-powered classification of signin vs dinein pages using Gemini 2.0 Flash Lite
- **Image Preprocessing**: Automatic deskewing and enhancement for better OCR accuracy
- **AI-Powered OCR**: Google Gemini 2.5 Flash for text extraction from signin pages
- **Rule-Based Classification**: Deterministic credential matching (no AI inference)
- **Modular Architecture**: Clean separation of concerns with reusable services
- **Database Integration**: SQL Server connection for credential lookups
- **Excel Output**: Classified results exported to Excel with summary statistics

---

## 📁 Project Structure

```
ocr-2/
├── app/
│   ├── clients/                    # External API integrations
│   │   ├── __init__.py
│   │   └── gemini_client.py       # Google Gemini API wrapper
│   │
│   ├── constants/                  # Configuration and constants
│   │   ├── __init__.py
│   │   ├── config.py              # Application configuration
│   │   └── prompts.py             # OCR prompts and templates
│   │
│   ├── services/                   # Business logic services
│   │   ├── __init__.py
│   │   ├── classification_service.py    # Credential classification
│   │   ├── credential_service.py        # Database credential queries
│   │   ├── data_extraction_service.py   # CSV data processing
│   │   ├── database.py                  # Database connection manager
│   │   ├── image_processing_service.py  # Image preprocessing
│   │   ├── pdf_processing_service.py    # PDF splitting & classification
│   │   └── sis_concour.py              # Main orchestration
│   │
│   ├── input/                      # PDF input files
│   ├── output/                     # Output Excel files
│   ├── pages/                      # Extracted page images (signin/dinein)
│   ├── tables/                     # CSV data files
│   └── models/                     # Data models (future)
│
├── test_db_connection.py
├── test_persistent_connection.py
├── test_pdf_processing.py         # Test PDF processing pipeline
├── PossibleNames_to_Credential_Mapping.xlsx
├── .env                            # API keys and credentials
├── ARCHITECTURE.md                 # Detailed architecture docs
├── DEPENDENCIES.md                 # Module dependencies
└── QUICK_REFERENCE.md             # Quick start guide
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Conda environment manager
- Google Gemini API key
- SQL Server access (optional, for database features)

### Installation

1. **Clone the repository**
```bash
cd ocr-2
```

2. **Create and activate conda environment**
```bash
conda create -n test-env python=3.11
conda activate test-env
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
# Or install manually:
pip install pandas google-generativeai pillow opencv-python numpy python-dotenv pymssql openpyxl PyMuPDF fastapi uvicorn
```

4. **Configure environment variables**
Create a `.env` file:
```env
GEMINI_API_KEY=your_api_key_here
DB_SERVER=your_db_server
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

5. **Prepare input directory**
```bash
# Create input directory if it doesn't exist
mkdir -p app/input
# Place your PDF files in app/input/
```

### Running the Application

#### Option 1: API Server (Recommended)

Start the FastAPI server:
```bash
python main.py
```

The server will:
1. Process all PDFs in `app/input/` on startup
2. Extract and classify pages (signin vs dinein)
3. Make signin images available for processing

**API Endpoints:**
- `GET /` - API information
- `GET /health` - Health check
- `POST /process-signin-pages` - Process all signin pages from PDFs
- `POST /process-images` - Process uploaded image files

**Example API Usage:**
```bash
# Process signin pages extracted from PDFs
curl -X POST http://127.0.0.1:8080/process-signin-pages

# Or upload images directly
curl -X POST http://127.0.0.1:8080/process-images \
  -F "files=@image1.png" \
  -F "files=@image2.png"
```

#### Option 2: Standalone Script

```bash
python app/services/sis_concour.py
```

#### Option 3: Test PDF Processing

Test the PDF processing pipeline:
```bash
python test_pdf_processing.py
```

**Output:**
- Console: Progress updates and OCR results
- Images: Extracted pages in `app/pages/` (with signin/dinein classification)
- Excel: `app/output/OCR_Results_Classified_{expense_id}_{timestamp}.xlsx`

---

## 🏗️ Architecture

### Module Responsibilities

#### 1. **clients/** - External API Integrations
- **gemini_client.py**: Wrapper for Google Gemini API
  - Handles authentication and API calls
  - Methods: `generate_content()`, `process_ocr()`

#### 2. **constants/** - Configuration & Constants
- **config.py**: Centralized configuration (paths, settings)
- **prompts.py**: All AI/OCR prompts stored as constants

#### 3. **services/** - Business Logic
- **pdf_processing_service.py**: PDF splitting, page extraction, and classification
- **image_processing_service.py**: Image preprocessing (deskewing, enhancement)
- **data_extraction_service.py**: CSV data handling and HCP name extraction
- **classification_service.py**: Rule-based credential classification
- **database.py**: Singleton database connection manager
- **credential_service.py**: Database queries for credentials
- **sis_concour.py**: Main orchestration script

### Workflow

```
PDF Files in app/input/
        ↓
PDF Processing Service
    - Split PDF into pages
    - Save as {pdf_name}_page_{n}.png
        ↓
Page Classification (Gemini 2.0 Flash Lite)
    - Analyze each page
    - Classify as signin or dinein
    - Rename: {pdf_name}_page_{n}_signin.png or _dinein.png
        ↓
Signin Pages → Processing Pipeline
    |
    ├→ DataExtractionService → Extract HCP names (from CSV by expense ID)
    ├→ ImageProcessingService → Deskew & enhance image
    ├→ GeminiClient (2.5 Flash) → OCR extraction
    ├→ ClassificationService → Classify credentials
    └→ Excel Output (grouped by expense ID)
        ↓
Dinein Pages → Stored for future processing
```

**Expense ID Extraction**: 
- Filename format: `{ID}_HCP Spend_{EXPENSE_ID}_{OTHER_DATA}.pdf`
- Expense ID is extracted from the 3rd part (after 2nd underscore)
- Signin pages with same expense ID are merged in output

---

## 📊 Features in Detail

### PDF Processing
- **Automatic page splitting**: Converts PDF pages to high-quality images (300 DPI)
- **Page classification**: Uses Gemini 2.0 Flash Lite to classify signin vs dinein pages
- **Expense ID extraction**: Parses expense ID from PDF filename automatically
- **Batch processing**: Handles multiple PDFs and pages efficiently
- **Error handling**: Graceful failure with detailed error messages

### Page Classification (AI-Powered)
- **Model**: Gemini 2.0 Flash Lite (fast and cost-effective)
- **Signin page detection**: Looks for keywords like "name", "signature", "credential"
- **Dinein page detection**: Identifies menu items, prices, restaurant information
- **Naming convention**: Pages saved as `{pdf_name}_page_{n}_{classification}.png`

### Image Processing
- **Automatic deskewing**: Detects rotation angles < 10°
- **Contrast enhancement**: Improves text visibility
- **Sharpness enhancement**: Better character recognition

### OCR Processing
- **Gemini 2.5 Flash model**: High accuracy text extraction
- **Structured prompts**: Separate column processing
- **HCP name reference**: Uses expected names for better accuracy

### Credential Classification
- **Rule-based matching**: Exact string lookup (no AI)
- **Two-stage matching**: PossibleNames → Credential columns
- **Case-insensitive**: Normalized comparisons
- **Classifications**: HCP, Field Employee, Unknown

---

## 🔧 Configuration

### Modifying OCR Prompts
Edit `app/constants/prompts.py`:
```python
OCR_SIGNIN_PROMPT = """
Your custom prompt here...
{HCPs}  # Placeholder for HCP names
"""
```

### Updating Settings
Edit `app/constants/config.py`:
```python
CSV_PATH = "path/to/your/data.csv"
SIGNIN_IMAGE_PATH = "path/to/your/image.png"
MAX_ROTATION_ANGLE = 15
CONTRAST_ENHANCEMENT = 2.0
```

---

## 📈 Example Output

### Console Output
```
Initializing services...
✓ Loaded CSV with 1008 records
✓ Loaded 829 credential mappings
✓ Expense ID: gWin$pt8sY00RZ$sJrt$pWJhKhvJKbxyeHgSdg
✓ Found 2 HCP names: ['PETER GONTZES', 'Anthony Sammut']
✓ Loaded 237 HCP credential mappings for company_id=1

Processing signin sheet image...
✓ Skipping rotation (angle -90.00° too large), using original orientation
Running OCR with Gemini...

============================================================
OCR RESULTS:
============================================================
- Anthony Sammut, Rep
- PETER GONTZES, MD
- Cristian Sanchez, P.N
- Genesis Alvarado, MA
- Kim Tornilda, RN
... (10 entries total)
============================================================

Classifying credentials...

✅ Classified results saved to: OCR_Results_Classified.xlsx

Summary:
  Total entries: 10
  HCP: 4
  Field Employee: 1
  Unknown: 5

✅ Processing complete!
```

### Excel Output
| Name | Credential_OCR | Credential_Standardized | Classification |
|------|---------------|------------------------|----------------|
| PETER GONTZES | MD | Doctor of Medicine | HCP |
| Anthony Sammut | Rep | Field Representative | Field Employee |
| Cristian Sanchez | P.N | Unknown | Unknown |

---

## 🎯 Benefits of Modular Structure

| Aspect | Improvement |
|--------|-------------|
| **Code Organization** | Reduced main file from ~250 to ~77 lines |
| **Maintainability** | Clear separation of concerns |
| **Testability** | Each service can be unit tested |
| **Reusability** | Services can be imported anywhere |
| **Configuration** | Centralized settings in config.py |
| **Prompts** | Externalized for easy modification |

---

## 🔬 Usage Examples

### Using Individual Services

#### Image Processing
```python
from app.services.image_processing_service import ImageProcessingService

service = ImageProcessingService()
processed_image = service.deskew_image("path/to/image.png")
```

#### Classification
```python
from app.services.classification_service import ClassificationService

classifier = ClassificationService("mapping.xlsx")
results = classifier.classify_ocr_results(ocr_text)
classifier.save_results(results, "output.xlsx")
```

#### Data Extraction
```python
from app.services.data_extraction_service import DataExtractionService

data_service = DataExtractionService("data.csv")
hcp_names = data_service.get_hcp_names(expense_id)
```

---

## 🐛 Troubleshooting

### Import Errors
Ensure all `__init__.py` files exist:
- `app/__init__.py`
- `app/clients/__init__.py`
- `app/constants/__init__.py`
- `app/services/__init__.py`

### API Key Issues
Verify `.env` file contains valid `GEMINI_API_KEY`

### Database Connection
Check SQL Server credentials in `.env` file

---

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed architecture documentation
- **[DEPENDENCIES.md](DEPENDENCIES.md)** - Module dependencies and flow diagrams
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick start and reference guide

---

## 🔄 Development

### Adding a New Service

1. Create file in `app/services/`:
```python
"""Description of service."""

class MyNewService:
    def __init__(self):
        pass
    
    def process(self):
        pass
```

2. Import in `sis_concour.py`:
```python
from app.services.my_new_service import MyNewService
```

### Testing
```bash
# Test database connection
python test_db_connection.py

# Test persistent connection
python test_persistent_connection.py
```

---

## 📦 Dependencies

- **pandas**: Data manipulation and Excel I/O
- **google-generativeai**: Gemini API client
- **Pillow (PIL)**: Image processing
- **opencv-python (cv2)**: Advanced image operations
- **numpy**: Numerical operations
- **python-dotenv**: Environment variable management
- **pymssql**: SQL Server connection
- **openpyxl**: Excel file handling

---

## 🚀 Future Enhancements

- [ ] Add `models/` for data classes and schemas
- [ ] Implement unit tests in `tests/` directory
- [ ] Add logging service
- [ ] Create API layer for web service deployment
- [ ] Batch processing for multiple images
- [ ] Fuzzy matching for better credential recognition
- [ ] Web UI for interactive processing

---

## 📝 License

[Add your license information here]

## 👥 Contributors

[Add contributor information here]

---

## 📞 Support

For issues or questions, please refer to the documentation files or contact the development team.