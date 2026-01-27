"""Configuration settings for the OCR application."""

import os

# Project root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# CSV data paths
CSV_PATH = os.path.join(
    PROJECT_ROOT, 
    "app", "input", 
    "Extract_syneos_GSK_20260117000000.csv"
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
GEMINI_MODEL_NAME = "gemini-2.5-flash"

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
BATCH_SIZE = 50  # Number of images to process per batch (increased for faster processing)
MAX_WORKERS_PER_BATCH = 15  # Maximum parallel threads per batch (increased for better parallelism)
# For 100 images: 2 batches × 15 workers = faster processing with controlled resource usage

# Fuzzy matching configuration
FUZZY_MATCH_THRESHOLD = 80  # Minimum similarity score (0-100) for credential fuzzy matching
