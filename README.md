# Healthcare Signin Sheet OCR Processing System

A production-ready OCR application for processing healthcare signin sheets with intelligent credential classification, state-level compliance filtering, and batch processing capabilities.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)  
- [Features](#features)
- [System Flow](#system-flow)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Technical Details](#technical-details)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This system automates the extraction and classification of healthcare professional (HCP) information from signin sheets attached to expense reports. It processes PDF documents, identifies signin pages, extracts handwritten names and credentials using OCR, and classifies them according to state-specific compliance rules.

### Key Capabilities

- **Automated PDF Processing**: Convert PDFs to images and classify pages
- **Intelligent Page Classification**: Distinguish between signin sheets and dinein receipts
- **AI-Powered OCR**: Extract handwritten names and credentials using Google Gemini
- **State-Level Compliance**: Filter credentials based on venue location and state regulations
- **Batch Processing**: Handle multiple PDFs in parallel with optimized API usage
- **Company-Specific Rules**: Apply different credential mappings per company (GSK, AstraZeneca, Lilly)

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                              │
│  PDF Files → app/input/Data/                                   │
│  CSV Data → app/tables/Extract_syneos_GSK_*.csv               │
│  Credential Mappings → PossibleNames_to_Credential_Mapping.xlsx│
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESSING LAYER                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐│
│  │ PDF Processing   │  │ Image Processing │  │ OCR Service   ││
│  │ Service          │→ │ Service          │→ │ (Gemini API)  ││
│  └──────────────────┘  └──────────────────┘  └───────────────┘│
│           ↓                                          ↓          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐│
│  │ Data Extraction  │  │ Credential       │  │ Classification││
│  │ Service          │→ │ Service          │→ │ Service       ││
│  └──────────────────┘  └──────────────────┘  └───────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       OUTPUT LAYER                              │
│  Excel Files → app/output/OCR_Results_Classified_*.xlsx       │
│  Page Images → app/pages/*_signin.png / *_dinein.png          │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

- **Language**: Python 3.11+
- **OCR Engine**: Google Gemini (gemini-3-flash-preview, gemini-2.5-flash-lite)
- **Local OCR**: Tesseract OCR (fallback for page classification)
- **Image Processing**: PIL, OpenCV, PyMuPDF
- **Database**: SQL Server (credential data)
- **Data Processing**: Pandas, RapidFuzz
- **Parallelization**: ThreadPoolExecutor

---

## ✨ Features

### 1. **PDF Processing & Page Classification**

- **Automatic PDF Splitting**: Converts multi-page PDFs into individual page images
- **Dual Classification Strategy**:
  - **Primary**: Tesseract OCR with fuzzy keyword matching (fast, free)
  - **Fallback**: Gemini LLM classification (accurate, only when needed)
- **Batch Classification**: Processes 10 pages per API call (90% API cost reduction)
- **Caching**: Skips already processed PDFs

### 2. **OCR Extraction**

- **Intelligent Prompting**: Uses HCP names from expense data to guide extraction
- **Multi-Field Extraction**:
  - Names
  - Credentials (MD, RN, NP, PA, PharmD, etc.)
  - Company ID (from page header)
  - Field Employee identification
- **Rate Limiting**: 45 requests/minute to prevent API throttling

### 3. **State-Level Credential Filtering**

- **Compliance Rules**: Filters credentials based on venue state
- **Federal + State**: Includes both federal credentials and state-specific ones
- **Always-Valid Credentials**: IDs 1 & 2 are never filtered out
- **Per-Expense Filtering**: Each page gets its own credential filter (prevents race conditions)

### 4. **Credential Classification**

- **Three-Tier Matching**:
  1. **Exact Match**: PossibleNames lookup (100% confidence)
  2. **Credential Match**: Direct credential name match
  3. **Fuzzy Match**: RapidFuzz with 80% threshold (for OCR errors)
- **No AI Inference**: Purely rule-based classification (deterministic results)
- **Company-Specific**: Only matches credentials for detected company
- **Special Character Handling**: Removes punctuation for consistent matching

### 5. **Batch Processing**

- **Parallel Processing**: 8 concurrent workers for OCR
- **Isolated State**: Each page has its own classification service
- **Memory Management**: Processes PDFs in sub-batches
- **Progress Tracking**: Real-time logging with ETA calculations

---

## 🔄 System Flow

### Stage 1: PDF Processing & Page Classification

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Scan Data Folder for PDFs                                │
│    ↓                                                         │
│ 2. For Each PDF:                                            │
│    a. Check if already split (cache check)                  │
│    b. Convert PDF pages to images (300 DPI)                 │
│    c. Classify pages using Tesseract:                       │
│       - Check for keywords: "name", "signature", "credential"│
│       - Fuzzy matching (85% threshold)                      │
│    d. If NO signin pages found → Fallback to LLM:          │
│       - Batch classify (10 pages per API call)             │
│    e. Save pages: page_1_signin.png, page_2_dinein.png     │
│    ↓                                                         │
│ 3. Collect all signin page paths                           │
└──────────────────────────────────────────────────────────────┘
```

### Stage 2: OCR Processing & Classification (Per Signin Page)

```
┌──────────────────────────────────────────────────────────────┐
│ For Each Signin Page (8 parallel workers):                  │
│                                                              │
│ 1. Extract expense_id from filename                         │
│    Example: "gWin$pt8sc3zEgHtcCnH3jZn0yCPcLjvlyfg"         │
│    ↓                                                         │
│ 2. Get HCP names and credential hints from CSV             │
│    (Based on expense_id → ExpenseV3_ID lookup)             │
│    ↓                                                         │
│ 3. Preprocess image (deskew, enhance contrast)             │
│    ↓                                                         │
│ 4. Run OCR with Gemini API                                 │
│    Input: Prompt + Image                                    │
│    Output: Names, Credentials, Company ID                   │
│    ↓                                                         │
│ 5. Extract company_id from OCR results                     │
│    Example: "COMPANY_ID: 1" → GSK                          │
│    ↓                                                         │
│ 6. Create ISOLATED classification service                   │
│    (Prevents race conditions in parallel processing)        │
│    ↓                                                         │
│ 7. Get venue_state from CSV                                │
│    Lookup: expense_id → ExpenseV3_LocationSubdivision      │
│    Example: "Indiana"                                       │
│    ↓                                                         │
│ 8. Query database for valid credentials                    │
│    SQL: WHERE state IN ('federal', 'Indiana')              │
│         AND company_id = 1                                  │
│    Returns: [1, 2, 10, 15, 23, ...]                        │
│    ↓                                                         │
│ 9. Filter credential mapping                                │
│    Keep only: valid_credential_ids + [1, 2]                │
│    ↓                                                         │
│ 10. Classify OCR results                                   │
│     For each name+credential:                               │
│     - Remove special characters (M.D. → MD)                │
│     - Exact match in PossibleNames                         │
│     - Exact match in Credential                            │
│     - Fuzzy match (≥80% similarity)                        │
│     - Default to Non-HCP                                    │
│     ↓                                                         │
│ 11. Return classified results                              │
│     {name, credential, classification, match_score}         │
└──────────────────────────────────────────────────────────────┘
```

### Stage 3: Result Aggregation & Export

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Group results by expense_id                              │
│    ↓                                                         │
│ 2. Combine pages from same expense                          │
│    ↓                                                         │
│ 3. Remove duplicate names (case-insensitive)                │
│    ↓                                                         │
│ 4. Save to Excel: OCR_Results_Classified_{expense_id}.xlsx │
│    Columns:                                                  │
│    - Name, Credential_OCR, Credential_Standardized          │
│    - Classification, Match_Score, Match_Method              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📦 Installation

### Prerequisites

- Python 3.11 or higher
- Conda (recommended) or venv
- Tesseract OCR installed
- SQL Server access (for credential database)
- Google Gemini API key

### Step 1: Clone Repository

```bash
cd c:\Users\abeeha.baig\OneDrive - Qordata\Desktop\ocr-2
```

### Step 2: Create Conda Environment

```bash
conda create -n test-env python=3.11
conda activate test-env
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Manual installation:**
```bash
pip install pandas google-generativeai pillow opencv-python numpy python-dotenv pymssql openpyxl PyMuPDF rapidfuzz pytesseract psutil
```

### Step 4: Install Tesseract OCR

**Windows:**
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to: `C:\Users\abeeha.baig\AppData\Local\Programs\Tesseract-OCR\`
3. Verify path in `app/constants/config.py`

### Step 5: Configure Environment Variables

Create `.env` file in project root:

```env
# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Database Connection
DB_SERVER=your_sql_server_address
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password
```

---

## ⚙️ Configuration

### File: `app/constants/config.py`

#### Data Paths

```python
# CSV data source
CSV_PATH = "app/input/Extract_syneos_GSK_20260117000000.csv"

# PDF input directory
INPUT_DIR = "app/input"

# Credential mapping
CREDENTIAL_MAPPING_FILE = "app/tables/PossibleNames_to_Credential_Mapping.xlsx"

# Output directories
OUTPUT_DIR = "app/output"
PAGES_DIR = "app/pages"
```

#### Processing Configuration

```python
# Batch processing
BATCH_SIZE = 20                    # Images per batch
MAX_WORKERS_PER_BATCH = 8         # Parallel OCR workers
PDF_BATCH_SIZE = 10               # PDFs per sub-batch

# Classification
MAX_CLASSIFICATION_WORKERS = 8     # Page classification workers
MAX_CLASSIFICATION_BATCH_SIZE = 10 # Pages per classification API call
FUZZY_MATCH_THRESHOLD = 80        # Minimum similarity score (0-100)

# Tesseract path
TESSERACT_PATH = r"C:\Users\abeeha.baig\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
```

#### Gemini Model Selection

```python
# OCR model (high quality)
GEMINI_MODEL_NAME = "gemini-3-flash-preview"

# Classification model (fast, cheaper)
# Used in pdf_processing_service.py:
classification_model = genai.GenerativeModel("gemini-2.5-flash-lite")
```

---

## 🚀 Usage

### Batch Processing (Recommended)

Process all PDFs in the Data folder:

```bash
python process_batch.py
```

**Expected Output:**

```
============================================================
BATCH PROCESSING - OCR FOR ALL FILES IN DATA FOLDER
============================================================
Start Time: 2026-02-10 14:30:00
Data Folder: c:\Users\...\ocr-2\app\input\Data
Concur CSV: c:\Users\...\ocr-2\app\tables\Extract_syneos_GSK_20260131000000.csv
Output Directory: c:\Users\...\ocr-2\app\output
============================================================

[DISCOVERY] Found files in Data folder:
  - PDF files: 50
  - Image files: 0
  - Total: 50

[STAGE 1/3] PROCESSING FILES
============================================================

[PART 1A] PROCESSING 50 PDFs IN PARALLEL
Processing in batches of 10 PDFs

[PDF BATCH 1/5] Processing PDFs 1-10 in parallel
------------------------------------------------------------
  [1/50] 1F606C186AB64BE5ADA9_HCP Spend_gWin$pt8sc3zEgHt...pdf
      [Expense ID] gWin$pt8sc3zEgHtcCnH3jZn0yCPcLjvlyfg
      [PDF→Images] Converting 3 pages...
      [OK] Extracted 3 pages
      [Tesseract Classification] Classifying 3 pages in parallel...
        [3/3] Tesseract: signin=1, dinein=2
      [Tesseract Complete] Signin: 1 | Dinein: 2
      [Saving] Saving 3 classified pages...
      [OK] Saved: 1 signin, 2 dinein

[STAGE 2/3] OCR PROCESSING
============================================================
[OCR PROCESSING] Starting parallel OCR on 45 signin pages
[OCR PROCESSING] Workers: 8

    [OCR 1] Running Gemini OCR...
    [OCR 1] Creating isolated classification service for company_id=1
    [OCR 1] State filter applied: Indiana (8 valid creds)
    [OCR 1] [OK] Complete: 12 records in 4.2s

  [PROGRESS] 5/45 pages (11.1%) | Success: 5 | Failed: 0 | ETA: 8.5m
  [PROGRESS] 10/45 pages (22.2%) | Success: 10 | Failed: 0 | ETA: 7.2m
  ...
  [PROGRESS] 45/45 pages (100.0%) | Success: 45 | Failed: 0 | ETA: 0.0m

[OCR COMPLETE] All 45 signin pages processed
  [OK] Successful: 45/45 (100.0%)
  [FAIL] Failed: 0/45
  ⏱ Total time: 8.3 minutes (498.0 seconds)
  ⚡ Avg per page: 11.1s
  🚀 Throughput: 5.4 pages/minute

[STAGE 3/3] GROUPING AND SAVING RESULTS
============================================================
Processing 45 results for 12 unique expenses...
  [Expense 1/12] gWin$pt8sc3zEgHtcCnH3jZn0yCPcLjvlyfg: 4 pages → 48 entries
  [Expense 2/12] gWin$pt80e1TNZTYzlKUwXRxRRbeucDUvhSQ: 3 pages → 36 entries
  ...

✅ All results saved to app/output/
```

### Single PDF Testing

```bash
python test_pdf_processing.py
```

---

## 📂 Project Structure

```
ocr-2/
├── app/
│   ├── clients/
│   │   ├── __init__.py
│   │   └── gemini_client.py              # Gemini API wrapper with rate limiting
│   │
│   ├── constants/
│   │   ├── __init__.py
│   │   ├── config.py                     # All configuration settings
│   │   └── prompts.py                    # OCR prompt templates
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classification_service.py     # Credential classification logic
│   │   ├── credential_service.py         # Database queries for credentials
│   │   ├── data_extraction_service.py    # CSV data processing & venue state
│   │   ├── database.py                   # SQL Server connection manager
│   │   ├── image_processing_service.py   # Image preprocessing (deskew, enhance)
│   │   ├── pdf_processing_service.py     # PDF splitting & page classification
│   │   └── sis_concour.py               # Legacy orchestration
│   │
│   ├── input/
│   │   ├── Data/                         # PDF files go here
│   │   └── Extract_syneos_GSK_*.csv     # Sample CSV data
│   │
│   ├── output/                           # Excel files generated here
│   │   └── OCR_Results_Classified_*.xlsx
│   │
│   ├── pages/                            # Extracted page images
│   │   ├── *_page_1_signin.png
│   │   └── *_page_2_dinein.png
│   │
│   └── tables/
│       ├── Extract_syneos_GSK_20260131000000.csv  # Expense data
│       └── PossibleNames_to_Credential_Mapping.xlsx
│
├── process_batch.py                      # Main batch processing script
├── test_pdf_processing.py               # Test script
├── requirements.txt                      # Python dependencies
├── .env                                  # Environment variables (not in repo)
└── README.md                            # This file
```

## 📊 Performance Metrics

### Typical Processing Times

| Task | Time per Item | Throughput |
|------|--------------|------------|
| PDF → Image conversion | 0.5s/page | 120 pages/min |
| Tesseract classification | 0.2s/page | 300 pages/min |
| LLM batch classification (10 pages) | 3-5s/batch | 120-200 pages/min |
| OCR extraction | 3-5s/page | 12-20 pages/min |
| Credential classification | 0.1s/page | 600 pages/min |

### Resource Usage

- **Memory**: ~2-4 GB for 50 PDFs
- **CPU**: High during Tesseract OCR
- **Network**: ~10-20 MB API traffic per PDF
- **Disk**: ~50-100 MB images per PDF

---

## 📝 Best Practices

### 1. File Organization

```
app/input/Data/
├── 2026-02-10_Batch1/
│   ├── report1.pdf
│   ├── report2.pdf
│   └── ...
└── 2026-02-11_Batch2/
    └── ...
```

### 2. Logging

Monitor these files for troubleshooting:
- Console output (real-time progress)
- Error messages (printed to stderr)

### 3. Data Validation

Before processing:
- ✅ Check CSV has venue state data
- ✅ Verify database connection
- ✅ Ensure credential mappings are up to date
- ✅ Test with 1-2 PDFs first

### 4. API Key Management

- Never commit `.env` to version control
- Rotate API keys periodically
- Monitor API quotas and usage

---
