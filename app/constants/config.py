"""Configuration settings for the OCR application."""

import os

# Project root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# CSV data paths
CSV_PATH = os.path.join(
    PROJECT_ROOT, 
    "app", "tables", 
    "Extract_beigene_BEIGENE_20260202000000.csv"
)

# Directory paths
INPUT_DIR = os.path.join(PROJECT_ROOT, "app", "input")  # PDF input directory
PAGES_DIR = os.path.join(PROJECT_ROOT, "app", "pages")  # Extracted page images
SIGNIN_IMAGE_PATH = os.path.join(
    PAGES_DIR,
    "2DBC20CE104A400AAB8D_HCP Spend_gWin$pt8sY00RZ$sJrt$pWJhKhvJKbxyeHgSdg_7025 - ST-US - GSK - Vacancy Management (0325)_2025-10-27T170222.733_20251028061146.png"
)

# Credential mapping
CREDENTIAL_MAPPING_FILE = os.path.join(PROJECT_ROOT, "app", "tables", "PossibleNames_to_Credential_Mapping.xlsx")

# Output directory
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "app", "output")

# Gemini model configuration
# GEMINI_MODEL_NAME = "gemini-2.5-flash"  # Alternative model option
GEMINI_MODEL_NAME = "gemini-3-flash-preview"

# Tesseract OCR configuration
TESSERACT_PATH = r"C:\Users\abeeha.baig\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Image processing settings
MAX_ROTATION_ANGLE = 10  # Maximum angle for image deskewing
CONTRAST_ENHANCEMENT = 1.5
SHARPNESS_ENHANCEMENT = 1.5

# Database configuration (if using database fallback)
DB_CONFIG = {
    "company_id": 1,
    "classification_filter": "HCP"
}

# Batch processing configuration
BATCH_SIZE = 20  # Number of images to process per batch (reduced for 50 PDFs to manage memory)
MAX_WORKERS_PER_BATCH = 8  # Maximum parallel threads per batch (reduced to avoid API rate limits)
PDF_BATCH_SIZE = 10  # Process PDFs in sub-batches to manage memory

# Classification configuration
MAX_CLASSIFICATION_WORKERS = 8  # Parallel workers for page classification
MAX_CLASSIFICATION_BATCH_SIZE = 10  # Number of pages to classify per API call (batch classification)
MAX_CLASSIFICATION_WORKERS = 5  # Parallel workers for page classification
# For 100 signin pages: 5 batches × 8 workers = controlled processing with ~40 min total time

# Timeout configuration
GEMINI_API_TIMEOUT = 120  # Timeout in seconds for individual Gemini API calls (2 minutes)
JOB_TIMEOUT = 3600  # Total job timeout in seconds (1 hour)
MAX_PDFS_PER_REQUEST = 50  # Maximum PDFs allowed per API request

# Fuzzy matching configuration
FUZZY_MATCH_THRESHOLD = 80  # Minimum similarity score (0-100) for credential fuzzy matching
