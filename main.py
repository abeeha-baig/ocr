"""FastAPI application for OCR processing of signin sheets."""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict
import os
import sys
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
from datetime import datetime
import psutil
import shutil
import gc

from app.clients.gemini_client import GeminiClient
from app.services.image_processing_service import ImageProcessingService
from app.services.classification_service import ClassificationService
from app.services.data_extraction_service import DataExtractionService
from app.services.credential_service import CredentialService
from app.services.pdf_processing_service import PDFProcessingService
from app.constants.prompts import OCR_SIGNIN_PROMPT
from app.constants.config import (
    CSV_PATH, 
    CREDENTIAL_MAPPING_FILE,
    OUTPUT_DIR,
    PROJECT_ROOT,
    DB_CONFIG,
    BATCH_SIZE,
    MAX_WORKERS_PER_BATCH,
    PDF_BATCH_SIZE,
    MAX_CLASSIFICATION_WORKERS,
    GEMINI_API_TIMEOUT,
    JOB_TIMEOUT,
    MAX_PDFS_PER_REQUEST,
    INPUT_DIR,
    PAGES_DIR,
    FUZZY_MATCH_THRESHOLD
)

# Initialize services once at startup
data_service = None
image_service = None
gemini_client = None
classification_service = None
pdf_processing_service = None
signin_image_paths = []  # Store paths of signin images to process

# Job storage for async processing (use Redis/database in production)
jobs: Dict[str, Dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global data_service, image_service, gemini_client, classification_service, pdf_processing_service, signin_image_paths
    
    try:
        print("Initializing services...")
        
        # Check if credential mapping file exists, if not create it FIRST
        credential_file_path = CREDENTIAL_MAPPING_FILE
        
        if not os.path.exists(credential_file_path):
            print(f"\n⚠️  Credential mapping file not found: {credential_file_path}")
            print("Creating credential mapping file from database (including CredentialOCR data)...")
            
            os.makedirs(os.path.dirname(credential_file_path), exist_ok=True)
            
            with CredentialService() as credential_service:
                # Fetch combined mappings (PossibleNames + CredentialOCR)
                mapping_df = credential_service.get_combined_credential_mapping()
                
                # Save to Excel file
                mapping_df.to_excel(credential_file_path, index=False)
                print(f"✓ Created credential mapping file: {credential_file_path}")
                print(f"✓ Total credential mappings: {len(mapping_df)}")
                print(f"  - Includes PossibleNames + CredentialOCR from tbl_SIS_CredentialMapping")
        else:
            print(f"✓ Credential mapping file exists: {credential_file_path}")
        
        # Now initialize services (ClassificationService will load the file)
        data_service = DataExtractionService(CSV_PATH)
        image_service = ImageProcessingService()
        gemini_client = GeminiClient()
        classification_service = ClassificationService(credential_file_path, fuzzy_threshold=FUZZY_MATCH_THRESHOLD)
        pdf_processing_service = PDFProcessingService(gemini_client, PAGES_DIR)
        
        # Load credentials once
        data_service.load_hcp_credentials(credential_file_path)
        
        print("✓ Services initialized successfully")
        print("✓ Ready to process PDFs via API\n")
        
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
            "process_images": "/process-images (POST) - Upload PDF files to process"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    memory = psutil.virtual_memory()
    return {
        "status": "healthy",
        "services": {
            "data_service": data_service is not None,
            "image_service": image_service is not None,
            "gemini_client": gemini_client is not None,
            "classification_service": classification_service is not None
        },
        "memory": {
            "percent": memory.percent,
            "available_gb": round(memory.available / (1024**3), 2),
            "total_gb": round(memory.total / (1024**3), 2)
        }
    }


def check_memory():
    """Check if sufficient memory is available."""
    memory = psutil.virtual_memory()
    print(f"[MEMORY] Current usage: {memory.percent}% ({memory.available / (1024**3):.2f} GB available)", flush=True)
    
    if memory.percent > 85:
        raise HTTPException(
            status_code=503,
            detail=f"Server memory critically low ({memory.percent}% used). Please try again later."
        )
    return memory.percent


@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """
    Check processing status of a job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Job status information
    """
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    return jobs[job_id]


def process_single_image(image_path: str, filename: str, page_idx: int = 0) -> dict:
    """Process a single signin sheet image with optimized logging for parallel execution."""
    start_time = time.time()
    try:
        print(f"    [OCR {page_idx}] Started: {filename}", flush=True)
        
        # Extract expense ID from image filename
        expense_id = data_service.extract_expense_id_from_filename(image_path)
        
        # Get HCP names for this expense
        hcp_names = data_service.get_hcp_names(expense_id)
        print(f"    [OCR {page_idx}] Found {len(hcp_names)} HCP names for {expense_id[:20]}...", flush=True)
        
        # Process image with OCR
        processed_image = image_service.deskew_image(image_path)
        
        # Prepare prompt with HCP names
        prompt = OCR_SIGNIN_PROMPT.format(HCPs=hcp_names)
        
        # Run OCR
        print(f"    [OCR {page_idx}] Running Gemini OCR...", flush=True)
        ocr_results = gemini_client.process_ocr(prompt, processed_image)
        
        # Extract company_id from OCR results
        company_id = data_service.extract_company_id_from_ocr(ocr_results)
        
        # Reload classification service with the correct company_id
        classification_service.reload_with_company_id(company_id)
        
        # Classify credentials
        classified_results = classification_service.classify_ocr_results(ocr_results)
        
        # Format results in a cleaner way (don't save yet)
        names_found = []
        if not classified_results.empty:
            for _, row in classified_results.iterrows():
                name = row.get('Name', 'Unknown')
                credential = row.get('Credential_Standardized', row.get('Credential_OCR', 'N/A'))
                classification = row.get('Classification', 'Unknown')
                names_found.append(f"{name}, {credential} [{classification}]")
        
        processing_time = time.time() - start_time
        print(f"    [OCR {page_idx}] ✓ Complete: {len(classified_results)} records in {processing_time:.1f}s", flush=True)
        
        return {
            "filename": filename,
            "expense_id": expense_id,
            "names_found": names_found,
            "classified_results": classified_results,
            "processing_time_seconds": round(processing_time, 2)
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        print(f"    [OCR {page_idx}] ✗ Failed: {filename} - {str(e)[:100]}", flush=True)
        return {
            "filename": filename,
            "expense_id": None,
            "names_found": [],
            "classified_results": None,
            "processing_time_seconds": round(processing_time, 2),
            "error": str(e)
        }


@app.post("/process-images")
async def process_images(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Submit PDF files for processing and return job ID immediately.
    Processing happens in the background.
    
    Args:
        background_tasks: FastAPI background tasks
        files: List of PDF files to process
        
    Returns:
        Job ID and status URL for tracking progress
    """
    print(f"\n{'='*80}", flush=True)
    print(f"[API REQUEST] Received {len(files)} PDF file(s) for processing", flush=True)
    print(f"{'='*80}\n", flush=True)
    
    # Check memory before starting
    check_memory()
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Validate file count
    if len(files) > MAX_PDFS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_PDFS_PER_REQUEST} PDFs allowed per request. You submitted {len(files)} PDFs."
        )
    
    # Validate file types - only PDFs
    print(f"[VALIDATION] Checking file types...", flush=True)
    for file in files:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext != '.pdf':
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.filename}. Only PDF files are accepted."
            )
    print(f"✓ All files are valid PDFs\n", flush=True)
    
    # Create job
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": {
            "current": 0,
            "total_pdfs": len(files),
            "signin_pages_found": 0,
            "signin_pages_processed": 0,
            "current_stage": "queued"
        },
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None
    }
    
    print(f"[JOB CREATED] Job ID: {job_id}", flush=True)
    print(f"[JOB CREATED] Total PDFs: {len(files)}", flush=True)
    print(f"[JOB CREATED] Status URL: /job-status/{job_id}\n", flush=True)
    
    # Start background processing
    background_tasks.add_task(process_pdfs_background, job_id, files)
    
    print(f"[BACKGROUND TASK] Processing started in background", flush=True)
    print(f"{'='*80}\n", flush=True)
    
    # Return immediately
    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Processing started for {len(files)} PDF(s)",
        "status_url": f"/job-status/{job_id}",
        "instructions": "Poll the status_url to check progress. Processing may take 30-60 minutes for 50 PDFs."
    }
    
async def process_pdfs_background(job_id: str, files: List[UploadFile]):
    """
    Background task to process PDFs in batches with comprehensive logging.
    
    Args:
        job_id: Unique job identifier
        files: List of uploaded PDF files
    """
    temp_dir = None
    total_start_time = time.time()
    
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["started_at"] = datetime.now().isoformat()
        jobs[job_id]["progress"]["current_stage"] = "initializing"
        
        print(f"\n{'='*80}", flush=True)
        print(f"[JOB {job_id[:8]}] STARTING BACKGROUND PROCESSING", flush=True)
        print(f"{'='*80}\n", flush=True)
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        print(f"[SETUP] Created temporary directory: {temp_dir}", flush=True)
        
        # Check initial memory
        check_memory()
        
        # Save all PDF files first
        print(f"\n[STAGE 1/4] UPLOADING PDFs TO TEMPORARY STORAGE", flush=True)
        print(f"{'='*80}", flush=True)
        jobs[job_id]["progress"]["current_stage"] = "uploading"
        
        pdf_paths = []
        for idx, file in enumerate(files, 1):
            temp_path = os.path.join(temp_dir, file.filename)
            with open(temp_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
                file_size_mb = len(content) / (1024 * 1024)
            pdf_paths.append((temp_path, file.filename))
            print(f"  [{idx}/{len(files)}] ✓ Saved: {file.filename} ({file_size_mb:.2f} MB)", flush=True)
        
        print(f"✓ All {len(files)} PDF files saved\n", flush=True)
        
        # Process PDFs in sub-batches to manage memory
        print(f"[STAGE 2/4] EXTRACTING AND CLASSIFYING PAGES", flush=True)
        print(f"{'='*80}", flush=True)
        print(f"Processing in sub-batches of {PDF_BATCH_SIZE} PDFs to manage memory", flush=True)
        jobs[job_id]["progress"]["current_stage"] = "extracting_pages"
        
        all_signin_pages = []
        num_pdf_batches = (len(pdf_paths) + PDF_BATCH_SIZE - 1) // PDF_BATCH_SIZE
        
        for batch_idx in range(num_pdf_batches):
            batch_start = batch_idx * PDF_BATCH_SIZE
            batch_end = min(batch_start + PDF_BATCH_SIZE, len(pdf_paths))
            batch_pdf_paths = pdf_paths[batch_start:batch_end]
            
            print(f"\n[PDF BATCH {batch_idx + 1}/{num_pdf_batches}] Processing PDFs {batch_start + 1}-{batch_end}", flush=True)
            print(f"-" * 80, flush=True)
            
            for pdf_idx, (temp_path, filename) in enumerate(batch_pdf_paths, start=batch_start + 1):
                try:
                    print(f"\n  [{pdf_idx}/{len(pdf_paths)}] {filename}", flush=True)
                    results = pdf_processing_service.process_pdf(temp_path)
                    signin_pages = results.get('signin', [])
                    dinein_pages = results.get('dinein', [])
                    all_signin_pages.extend(signin_pages)
                    
                    print(f"      ✓ Extracted: {len(signin_pages)} signin + {len(dinein_pages)} dinein pages", flush=True)
                    
                    # Update progress
                    jobs[job_id]["progress"]["current"] = pdf_idx
                    jobs[job_id]["progress"]["signin_pages_found"] = len(all_signin_pages)
                    
                    # Clean up processed PDF immediately to free memory
                    os.remove(temp_path)
                    
                except Exception as e:
                    print(f"      ❌ Failed: {e}", flush=True)
                    continue
            
            # Force garbage collection after each batch
            print(f"\n  [MEMORY] Cleaning up after batch {batch_idx + 1}...", flush=True)
            gc.collect()
            check_memory()
        
        print(f"\n{'='*80}", flush=True)
        print(f"✓ EXTRACTION COMPLETE", flush=True)
        print(f"  Total signin pages found: {len(all_signin_pages)}", flush=True)
        print(f"{'='*80}\n", flush=True)
        
        # If no signin pages found, complete the job successfully with no results
        if not all_signin_pages:
            print(f"⚠️  No signin pages found in any PDFs - job completing with no results", flush=True)
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["completed_at"] = datetime.now().isoformat()
            jobs[job_id]["progress"]["current_stage"] = "completed"
            jobs[job_id]["result"] = {
                "total_processing_time_seconds": round(time.time() - total_start_time, 2),
                "pdfs_processed": len(files),
                "signin_pages_found": 0,
                "signin_pages_processed": 0,
                "failed": 0,
                "unique_expense_ids": 0,
                "output_files": [],
                "message": "No signin pages found in the uploaded PDFs. All pages were classified as dinein or other types."
            }
            return
        
        jobs[job_id]["progress"]["signin_pages_found"] = len(all_signin_pages)
        
        # Process signin pages in batches
        print(f"[STAGE 3/4] PROCESSING SIGNIN PAGES WITH OCR", flush=True)
        print(f"{'='*80}", flush=True)
        print(f"Processing {len(all_signin_pages)} signin pages in batches of {BATCH_SIZE}", flush=True)
        print(f"Using {MAX_WORKERS_PER_BATCH} parallel workers per batch", flush=True)
        jobs[job_id]["progress"]["current_stage"] = "ocr_processing"
        
        all_results = await process_signin_pages_batch(all_signin_pages, job_id)
        
        # Group results by expense ID
        print(f"\n[STAGE 4/4] COMBINING AND SAVING RESULTS", flush=True)
        print(f"{'='*80}", flush=True)
        jobs[job_id]["progress"]["current_stage"] = "saving_results"
        
        expense_groups = {}
        for result in all_results:
            if "error" in result or result.get('classified_results') is None:
                continue
            
            expense_id = result['expense_id']
            if expense_id not in expense_groups:
                expense_groups[expense_id] = []
            expense_groups[expense_id].append(result['classified_results'])
        
        # Combine and save results per expense ID
        import pandas as pd
        saved_files = []
        
        for idx, (expense_id, results_list) in enumerate(expense_groups.items(), 1):
            combined_df = pd.concat(results_list, ignore_index=True)
            combined_df = classification_service.remove_duplicate_names(combined_df)
            output_file = classification_service.save_results(combined_df, expense_id)
            saved_files.append(output_file)
            print(f"  [{idx}/{len(expense_groups)}] ✓ Saved {len(combined_df)} records for expense ID: {expense_id}", flush=True)
        
        # Calculate final statistics
        total_time = time.time() - total_start_time
        successful = sum(1 for r in all_results if "error" not in r)
        failed = len(all_results) - successful
        
        print(f"\n{'='*80}", flush=True)
        print(f"✅ JOB COMPLETE - Job ID: {job_id[:8]}", flush=True)
        print(f"{'='*80}", flush=True)
        print(f"  PDFs processed: {len(files)}", flush=True)
        print(f"  Signin pages found: {len(all_signin_pages)}", flush=True)
        print(f"  Signin pages processed: {successful}/{len(all_signin_pages)}", flush=True)
        print(f"  Failed: {failed}", flush=True)
        print(f"  Unique expense IDs: {len(expense_groups)}", flush=True)
        print(f"  Output files saved: {len(saved_files)}", flush=True)
        print(f"  Total time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)", flush=True)
        print(f"  Avg time per PDF: {total_time/len(files):.1f} seconds", flush=True)
        print(f"{'='*80}\n", flush=True)
        
        # Update job status
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        jobs[job_id]["progress"]["current_stage"] = "completed"
        jobs[job_id]["progress"]["signin_pages_processed"] = successful
        jobs[job_id]["result"] = {
            "total_processing_time_seconds": round(total_time, 2),
            "total_processing_time_minutes": round(total_time / 60, 2),
            "pdfs_processed": len(files),
            "signin_pages_found": len(all_signin_pages),
            "signin_pages_processed": successful,
            "failed": failed,
            "unique_expense_ids": len(expense_groups),
            "output_files": saved_files,
            "message": f"Processing complete! {successful}/{len(all_signin_pages)} pages processed successfully."
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n{'='*80}", flush=True)
        print(f"❌ JOB FAILED - Job ID: {job_id[:8]}", flush=True)
        print(f"{'='*80}", flush=True)
        print(f"Error: {error_msg}", flush=True)
        print(f"{'='*80}\n", flush=True)
        
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        jobs[job_id]["error"] = error_msg
        
    finally:
        # Cleanup temporary files
        if temp_dir and os.path.exists(temp_dir):
            try:
                print(f"[CLEANUP] Removing temporary directory...", flush=True)
                shutil.rmtree(temp_dir)
                print(f"✓ Cleanup complete\n", flush=True)
            except Exception as e:
                print(f"⚠️  Warning: Could not cleanup temp directory: {e}\n", flush=True)


async def process_signin_pages_batch(signin_pages: List[str], job_id: str) -> List[dict]:
    """
    Process ALL signin pages with continuous parallel processing (no batching delays).
    
    Args:
        signin_pages: List of signin page paths
        job_id: Job identifier for progress tracking
        
    Returns:
        List of processing results
    """
    total_pages = len(signin_pages)
    print(f"\n[OCR PROCESSING] Starting continuous parallel OCR on {total_pages} signin pages", flush=True)
    print(f"[OCR PROCESSING] Workers: {MAX_WORKERS_PER_BATCH} | Submitting all tasks to queue...", flush=True)
    print(f"=" * 80, flush=True)
    
    all_results = []
    completed = 0
    successful = 0
    failed = 0
    
    loop = asyncio.get_event_loop()
    overall_start_time = time.time()
    
    # Submit ALL OCR tasks at once - ThreadPoolExecutor manages the queue
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_PER_BATCH) as executor:
        # Create all futures at once
        futures = {
            loop.run_in_executor(
                executor, 
                process_single_image, 
                page_path, 
                Path(page_path).name,
                idx + 1
            ): idx
            for idx, page_path in enumerate(signin_pages)
        }
        
        print(f"[OCR PROCESSING] All {total_pages} tasks submitted. Workers are processing continuously...", flush=True)
        print(f"=" * 80, flush=True)
        
        # Process results as they complete (continuous parallel processing)
        for future in asyncio.as_completed(futures.keys()):
            try:
                result = await future
                completed += 1
                
                if "error" not in result:
                    successful += 1
                else:
                    failed += 1
                
                all_results.append(result)
                
                # Log progress every 5 pages or at milestones
                if completed % 5 == 0 or completed in [1, total_pages]:
                    elapsed = time.time() - overall_start_time
                    avg_time = elapsed / completed
                    eta_seconds = avg_time * (total_pages - completed)
                    progress_pct = (completed / total_pages) * 100
                    
                    print(f"  [PROGRESS] {completed}/{total_pages} pages ({progress_pct:.1f}%) | "
                          f"Success: {successful} | Failed: {failed} | "
                          f"ETA: {eta_seconds/60:.1f}m", flush=True)
                
                # Update job progress
                jobs[job_id]["progress"]["signin_pages_processed"] = completed
                
            except Exception as e:
                completed += 1
                failed += 1
                page_idx = futures[future]
                print(f"  [ERROR] Page {page_idx + 1} failed: {e}", flush=True)
                all_results.append({
                    "filename": signin_pages[page_idx],
                    "error": str(e)
                })
    
    total_time = time.time() - overall_start_time
    
    print(f"\n{'=' * 80}", flush=True)
    print(f"[OCR COMPLETE] All {total_pages} signin pages processed", flush=True)
    print(f"  ✓ Successful: {successful}/{total_pages} ({successful/total_pages*100:.1f}%)", flush=True)
    print(f"  ✗ Failed: {failed}/{total_pages}", flush=True)
    print(f"  ⏱ Total time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)", flush=True)
    print(f"  ⚡ Avg per page: {total_time/total_pages:.1f}s", flush=True)
    print(f"  🚀 Throughput: {(total_pages/total_time)*60:.1f} pages/minute", flush=True)
    print(f"{'=' * 80}\n", flush=True)
    
    # Check memory after completion
    check_memory()
    
    return all_results


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
