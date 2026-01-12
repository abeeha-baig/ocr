"""Main orchestration script for OCR processing of signin sheets."""

import os
import sys

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.clients.gemini_client import GeminiClient
from app.services.image_processing_service import ImageProcessingService
from app.services.classification_service import ClassificationService
from app.services.data_extraction_service import DataExtractionService
from app.constants.prompts import OCR_SIGNIN_PROMPT
from app.constants.config import (
    CSV_PATH, 
    SIGNIN_IMAGE_PATH, 
    CREDENTIAL_MAPPING_FILE,
    OUTPUT_DIR
)


def main():
    """Main orchestration function for OCR processing."""
    
    # Initialize services
    print("Initializing services...")
    data_service = DataExtractionService(CSV_PATH)
    image_service = ImageProcessingService()
    gemini_client = GeminiClient()
    classification_service = ClassificationService(CREDENTIAL_MAPPING_FILE)
    
    # Extract expense ID from image filename
    expense_id = data_service.extract_expense_id_from_filename(SIGNIN_IMAGE_PATH)
    print(f"✓ Expense ID: {expense_id}")
    
    # Get HCP names for this expense
    hcp_names = data_service.get_hcp_names(expense_id)
    print(f"✓ Found {len(hcp_names)} HCP names: {hcp_names}")
    
    # Load HCP credentials (for reference only, not used in current flow)
    hcp_credentials_df, hcp_credential_mapping = data_service.load_hcp_credentials(
        CREDENTIAL_MAPPING_FILE
    )
    
    # Process image with OCR
    print("\nProcessing signin sheet image...")
    processed_image = image_service.deskew_image(SIGNIN_IMAGE_PATH)
    
    # Prepare prompt with HCP names
    prompt = OCR_SIGNIN_PROMPT.format(HCPs=hcp_names)
    
    # Run OCR
    print("Running OCR with Gemini...")
    ocr_results = gemini_client.process_ocr(prompt, processed_image)
    
    print("\n" + "="*60)
    print("OCR RESULTS:")
    print("="*60)
    print(ocr_results)
    print("="*60)
    
    # Classify credentials
    print("\nClassifying credentials...")
    classified_results = classification_service.classify_ocr_results(ocr_results)
    
    # Save results
    classification_service.save_results(classified_results)
    
    print("\n✅ Processing complete!")
    return classified_results


if __name__ == "__main__":
    results = main()
