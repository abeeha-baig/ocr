"""Test script for PDF processing functionality."""

import os
from pathlib import Path
from app.clients.gemini_client import GeminiClient
from app.services.pdf_processing_service import PDFProcessingService
from app.constants.config import INPUT_DIR, PAGES_DIR

def test_pdf_processing():
    """Test PDF processing with a sample PDF."""
    print("="*60)
    print("PDF PROCESSING TEST")
    print("="*60)
    
    # Check if input directory exists
    if not os.path.exists(INPUT_DIR):
        print(f"\n❌ Input directory not found: {INPUT_DIR}")
        print("Creating input directory...")
        os.makedirs(INPUT_DIR, exist_ok=True)
        print(f"✓ Created: {INPUT_DIR}")
    else:
        print(f"\n✓ Input directory exists: {INPUT_DIR}")
    
    # Check for PDF files
    pdf_files = list(Path(INPUT_DIR).glob("*.pdf"))
    
    if not pdf_files:
        print(f"\n⚠️  No PDF files found in: {INPUT_DIR}")
        print("\nTo test:")
        print(f"1. Place PDF files in: {INPUT_DIR}")
        print("2. Run this test script again")
        return
    
    print(f"\n✓ Found {len(pdf_files)} PDF file(s):")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    
    # Initialize services
    print("\n" + "="*60)
    print("Initializing services...")
    print("="*60)
    
    try:
        gemini_client = GeminiClient()
        pdf_service = PDFProcessingService(gemini_client, PAGES_DIR)
        print("✓ Services initialized\n")
        
        # Process PDFs
        results = pdf_service.process_all_pdfs(INPUT_DIR)
        
        # Print summary
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60)
        print(f"Expense IDs found: {len(results)}")
        print(f"Total signin pages: {sum(len(pages) for pages in results.values())}")
        
        for expense_id, signin_pages in results.items():
            print(f"\n  Expense ID: {expense_id}")
            print(f"  Signin pages: {len(signin_pages)}")
            for page in signin_pages[:3]:  # Show first 3
                print(f"    - {Path(page).name}")
            if len(signin_pages) > 3:
                print(f"    ... and {len(signin_pages) - 3} more")
        
        print("\n" + "="*60)
        print("✅ TEST COMPLETE")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_pdf_processing()
