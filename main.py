"""FastAPI application for OCR processing of signin sheets."""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import os
import sys
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
    DB_CONFIG,
    BATCH_SIZE,
    MAX_WORKERS_PER_BATCH
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
    
    try:
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
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during startup: {e}")
        yield
    finally:
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
        print(f"\n{'='*60}", flush=True)
        print(f"[START] Processing: {filename}", flush=True)
        print(f"{'='*60}", flush=True)
        
        # Extract expense ID from image filename
        print(f"[STEP 1/6] Extracting expense ID from filename...", flush=True)
        expense_id = data_service.extract_expense_id_from_filename(image_path)
        print(f"✓ Expense ID: {expense_id}", flush=True)
        
        # Get HCP names for this expense
        hcp_names = data_service.get_hcp_names(expense_id)
        print(f"✓ Found {len(hcp_names)} HCP names: {hcp_names}")
        
        # Process image with OCR
        print(f"[STEP 3/6] Processing image (deskewing and enhancement)...", flush=True)
        processed_image = image_service.deskew_image(image_path)
        print(f"✓ Image preprocessing complete", flush=True)
        
        # Prepare prompt with HCP names
        prompt = OCR_SIGNIN_PROMPT.format(HCPs=hcp_names)
        
        # Run OCR
        print(f"[STEP 4/6] Running Gemini OCR (this may take 10-30 seconds)...", flush=True)
        ocr_results = gemini_client.process_ocr(prompt, processed_image)
        print(f"✓ OCR complete, extracted {len(ocr_results.split(chr(10)))} lines", flush=True)
        
        # Classify credentials
        print(f"[STEP 5/6] Classifying credentials...", flush=True)
        classified_results = classification_service.classify_ocr_results(ocr_results)
        print(f"✓ Classification complete: {len(classified_results)} records", flush=True)
        
        # Save results
        print(f"[STEP 6/6] Saving results to file...", flush=True)
        output_filename = classification_service.save_results(classified_results, expense_id)
        print(f"✓ Results saved to: {output_filename}", flush=True)
        
        # Format results in a cleaner way
        names_found = []
        if not classified_results.empty:
            for _, row in classified_results.iterrows():
                name = row.get('Name', 'Unknown')
                credential = row.get('Credential_Standardized', row.get('Credential_OCR', 'N/A'))
                classification = row.get('Classification', 'Unknown')
                names_found.append(f"{name}, {credential} [{classification}]")
        
        processing_time = time.time() - start_time
        print(f"\n[COMPLETE] {filename} processed in {processing_time:.2f}s", flush=True)
        print(f"{'='*60}\n", flush=True)
        return {
            "filename": filename,
            "names_found": names_found,
            "processing_time_seconds": round(processing_time, 2)
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        print(f"\n❌ [ERROR] Failed processing {filename}: {str(e)}", flush=True)
        print(f"{'='*60}\n", flush=True)
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
        print(f"\n{'='*60}", flush=True)
        print(f"API REQUEST: Processing {len(files)} image(s) in PARALLEL", flush=True)
        print(f"{'='*60}\n", flush=True)
        
        # Save all files first
        print(f"[UPLOAD] Saving uploaded files to temporary directory...", flush=True)
        file_paths = []
        for idx, file in enumerate(files, 1):
            temp_path = os.path.join(temp_dir, file.filename)
            with open(temp_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            file_paths.append((temp_path, file.filename))
            print(f"  [{idx}/{len(files)}] Saved: {file.filename}", flush=True)
        print(f"✓ All files saved to temp directory\n", flush=True)
        
        # Process images in batches with threading
        total_images = len(file_paths)
        num_batches = (total_images + BATCH_SIZE - 1) // BATCH_SIZE  # Ceiling division
        
        print(f"[PROCESSING] Processing {total_images} images in {num_batches} batch(es)")
        print(f"Batch size: {BATCH_SIZE}, Workers per batch: {MAX_WORKERS_PER_BATCH}\n", flush=True)
        
        loop = asyncio.get_event_loop()
        all_results = []
        
        for batch_num in range(num_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, total_images)
            batch_files = file_paths[start_idx:end_idx]
            
            print(f"{'='*60}", flush=True)
            print(f"[BATCH {batch_num + 1}/{num_batches}] Processing images {start_idx + 1}-{end_idx} of {total_images}", flush=True)
            print(f"{'='*60}\n", flush=True)
            
            batch_start_time = time.time()
            
            # Process batch in parallel
            with ThreadPoolExecutor(max_workers=MAX_WORKERS_PER_BATCH) as executor:
                tasks = [
                    loop.run_in_executor(executor, process_single_image, path, filename)
                    for path, filename in batch_files
                ]
                batch_results = await asyncio.gather(*tasks)
            
            # Track batch statistics
            batch_time = time.time() - batch_start_time
            batch_successful = sum(1 for r in batch_results if "error" not in r)
            batch_failed = len(batch_results) - batch_successful
            
            all_results.extend(batch_results)
            
            print(f"\n{'='*60}", flush=True)
            print(f"[BATCH {batch_num + 1}/{num_batches} COMPLETE]", flush=True)
            print(f"  Processed: {len(batch_results)} images", flush=True)
            print(f"  Successful: {batch_successful}", flush=True)
            print(f"  Failed: {batch_failed}", flush=True)
            print(f"  Time: {batch_time:.2f}s", flush=True)
            print(f"  Avg per image: {batch_time/len(batch_results):.2f}s", flush=True)
            print(f"{'='*60}\n", flush=True)
        
        results = all_results
        
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
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print("\n⚠️  Shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8080,
            reload=False,
            log_level="info"
        )
    except (KeyboardInterrupt, SystemExit):
        print("\n✓ Application stopped")
