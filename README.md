# OCR Application - Modular Architecture

A production-ready OCR application for processing healthcare signin sheets with credential classification.

## ✅ Project Overview

This application extracts names and credentials from signin sheet images using Google Gemini AI, then classifies credentials using rule-based matching against a database of known medical credentials.

### Key Features

- **Image Preprocessing**: Automatic deskewing and enhancement for better OCR accuracy
- **AI-Powered OCR**: Google Gemini 2.5 Flash for text extraction
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
│   │   └── sis_concour.py              # Main orchestration
│   │
│   ├── input/                      # Input files
│   ├── output/                     # Output files
│   ├── pages/                      # Image files
│   ├── tables/                     # CSV data files
│   └── models/                     # Data models (future)
│
├── test_db_connection.py
├── test_persistent_connection.py
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
pip install pandas google-generativeai pillow opencv-python numpy python-dotenv pymssql openpyxl
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

### Running the Application

```bash
python app/services/sis_concour.py
```

**Output:**
- Console: Progress updates and OCR results
- File: `OCR_Results_Classified.xlsx` with classified credentials

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
- **image_processing_service.py**: Image preprocessing (deskewing, enhancement)
- **data_extraction_service.py**: CSV data handling and HCP name extraction
- **classification_service.py**: Rule-based credential classification
- **database.py**: Singleton database connection manager
- **credential_service.py**: Database queries for credentials
- **sis_concour.py**: Main orchestration script

### Workflow

```
CSV Data + Image File
        ↓
DataExtractionService → Extract HCP names
        ↓
ImageProcessingService → Deskew & enhance image
        ↓
GeminiClient → OCR extraction
        ↓
ClassificationService → Classify credentials
        ↓
Excel Output
```

---

## 📊 Features in Detail

### Image Processing
- **Automatic deskewing**: Detects rotation angles < 10°
- **Contrast enhancement**: Improves text visibility
- **Sharpness enhancement**: Better character recognition

### OCR Processing
- **Gemini 2.5 Flash model**: High accuracy text extraction
- **Structured prompts**: Separate column processing
- **HCP name reference**: Uses expected names for better accuracy

### Classification
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