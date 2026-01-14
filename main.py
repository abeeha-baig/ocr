"""FastAPI application for OCR processing of signin sheets."""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import os
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from app.clients.gemini_client import GeminiClient
from app.services.image_processing_service import ImageProcessingService
from app.services.classification_service import ClassificationService
from app.services.data_extraction_service import DataExtractionService
from app.services.credential_service import CredentialService
from app.constants.prompts import OCR_SIGNIN_PROMPT
from app.constants.config import (
    CSV_PATH, 
    CREDENTIAL_MAPPING_FILE,
    OUTPUT_DIR,
    PROJECT_ROOT,
    DB_CONFIG
)

# Initialize services once at startup
data_service = None
image_service = None
gemini_client = None
classification_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global data_service, image_service, gemini_client, classification_service
    
    print("Initializing services...")
    
    # Check if credential mapping file exists, if not create it FIRST
    credential_file_path = CREDENTIAL_MAPPING_FILE
    
    if not os.path.exists(credential_file_path):
        print(f"\n⚠️  Credential mapping file not found: {credential_file_path}")
        print("Creating credential mapping file from database (all companies and credentials)...")
        
        os.makedirs(os.path.dirname(credential_file_path), exist_ok=True)
        
        with CredentialService() as credential_service:
            # Fetch all credential mappings (not filtered by company)
            mapping_df = credential_service.get_possible_names_to_credential_mapping()
            
            # Save to Excel file
            mapping_df.to_excel(credential_file_path, index=False)
            print(f"✓ Created credential mapping file: {credential_file_path}")
            print(f"✓ Total credential mappings: {len(mapping_df)}")
    else:
        print(f"✓ Credential mapping file exists: {credential_file_path}")
    
    # Now initialize services (ClassificationService will load the file)
    data_service = DataExtractionService(CSV_PATH)
    image_service = ImageProcessingService()
    gemini_client = GeminiClient()
    classification_service = ClassificationService(credential_file_path)
    
    # Load credentials once
    data_service.load_hcp_credentials(credential_file_path)
    
    print("✓ Services initialized successfully")
    yield
    print("Shutting down...")


app = FastAPI(
    title="OCR Signin Sheet Processor",
    description="API for processing signin sheet images with OCR and credential classification",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "OCR Signin Sheet Processor API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "process_images": "/process-images (POST)"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "data_service": data_service is not None,
            "image_service": image_service is not None,
            "gemini_client": gemini_client is not None,
            "classification_service": classification_service is not None
        }
    }


def process_single_image(image_path: str, filename: str) -> dict:
    """Process a single signin sheet image."""
    start_time = time.time()
    try:
        # Extract expense ID from image filename
        expense_id = data_service.extract_expense_id_from_filename(image_path)
        print(f"✓ Processing {filename} - Expense ID: {expense_id}")
        
        # Get HCP names for this expense
        hcp_names = data_service.get_hcp_names(expense_id)
        print(f"✓ Found {len(hcp_names)} HCP names: {hcp_names}")
        
        # Process image with OCR
        processed_image = image_service.deskew_image(image_path)
        
        # Prepare prompt with HCP names
        prompt = OCR_SIGNIN_PROMPT.format(HCPs=hcp_names)
        
        # Run OCR
        print(f"Running OCR on {filename}...")
        ocr_results = gemini_client.process_ocr(prompt, processed_image)
        
        # Classify credentials
        print(f"Classifying credentials for {filename}...")
        classified_results = classification_service.classify_ocr_results(ocr_results)
        
        # Save results
        output_filename = classification_service.save_results(classified_results, expense_id)
        
        # Format results in a cleaner way
        names_found = []
        if not classified_results.empty:
            for _, row in classified_results.iterrows():
                name = row.get('Name', 'Unknown')
                credential = row.get('Credential_Standardized', row.get('Credential_OCR', 'N/A'))
                classification = row.get('Classification', 'Unknown')
                names_found.append(f"{name}, {credential} [{classification}]")
        
        processing_time = time.time() - start_time
        return {
            "filename": filename,
            "names_found": names_found,
            "processing_time_seconds": round(processing_time, 2)
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        print(f"❌ Error processing {filename}: {str(e)}")
        return {
            "filename": filename,
            "names_found": [],
            "processing_time_seconds": round(processing_time, 2),
            "error": str(e)
        }


@app.post("/process-images")
async def process_images(files: List[UploadFile] = File(...)):
    """
    Process multiple signin sheet images.
    
    Args:
        files: List of image files to process
        
    Returns:
        JSON response with processing results for each image
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Validate file types
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.gif'}
    for file in files:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.filename}. Allowed: {', '.join(allowed_extensions)}"
            )
    
    temp_dir = tempfile.mkdtemp()
    total_start_time = time.time()
    
    try:
        print(f"\n{'='*60}")
        print(f"Processing {len(files)} image(s) in PARALLEL")
        print(f"{'='*60}\n")
        
        # Save all files first
        file_paths = []
        for file in files:
            temp_path = os.path.join(temp_dir, file.filename)
            with open(temp_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            file_paths.append((temp_path, file.filename))
        
        # Process all images in parallel using ThreadPoolExecutor
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=min(len(files), 5)) as executor:
            # Submit all tasks
            tasks = [
                loop.run_in_executor(executor, process_single_image, path, filename)
                for path, filename in file_paths
            ]
            # Wait for all to complete
            results = await asyncio.gather(*tasks)
        
        # Summary
        total_time = time.time() - total_start_time
        successful = sum(1 for r in results if "error" not in r)
        failed = len(results) - successful
        
        print(f"\n{'='*60}")
        print(f"✅ Batch processing complete!")
        print(f"Successful: {successful}/{len(files)}")
        print(f"Failed: {failed}/{len(files)}")
        print(f"Total time: {total_time:.2f}s")
        print(f"{'='*60}")
        
        return JSONResponse(content={
            "total_processing_time_seconds": round(total_time, 2),
            "images_processed": len(files),
            "successful": successful,
            "failed": failed,
            "results": results
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
        
    finally:
        # Cleanup temporary files
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Warning: Could not cleanup temp directory: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=False)
