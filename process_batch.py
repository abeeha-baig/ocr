"""Batch processing script for OCR on all files in the Data folder."""

import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import psutil
from datetime import datetime
import pandas as pd
from typing import List, Dict

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.clients.gemini_client import GeminiClient
from app.services.image_processing_service import ImageProcessingService
from app.services.classification_service import ClassificationService
from app.services.data_extraction_service import DataExtractionService
from app.services.pdf_processing_service import PDFProcessingService
from app.services.credential_service import CredentialService
from app.constants.prompts import OCR_SIGNIN_PROMPT
from app.constants.config import (
    CREDENTIAL_MAPPING_FILE,
    OUTPUT_DIR,
    PAGES_DIR,
    FUZZY_MATCH_THRESHOLD,
    MAX_WORKERS_PER_BATCH,
    PDF_BATCH_SIZE
)

# Configuration
DATA_FOLDER = os.path.join(project_root, "app", "input", "Data")
CONCUR_CSV_PATH = os.path.join(project_root, "app", "tables", "Extract_syneos_GSK_20260131000000.csv")
PDF_BATCH_SIZE_LOCAL = 10
MAX_OCR_WORKERS = 8


def check_memory():
    """Check and log current memory usage."""
    memory = psutil.virtual_memory()
    print(f"[MEMORY] {memory.percent}% used | {memory.available / (1024**3):.2f} GB available / {memory.total / (1024**3):.2f} GB total", flush=True)


def process_single_signin_page(page_path: str, filename: str, page_idx: int, 
                               data_service, image_service, gemini_client) -> Dict:
    """Process a single signin page with OCR and credential classification."""
    start_time = time.time()
    
    try:
        expense_id = data_service.extract_expense_id_from_filename(filename)
        if not expense_id:
            raise ValueError(f"Could not extract expense ID from filename: {filename}")
        
        hcp_names = data_service.get_hcp_names(expense_id)
        credential_hints = data_service.get_credential_hints(expense_id)
        processed_image = image_service.deskew_image(page_path)
        prompt = OCR_SIGNIN_PROMPT.format(HCPs=hcp_names, credential_hints=credential_hints)
        
        print(f"    [OCR {page_idx}] Running Gemini OCR...", flush=True)
        ocr_results = gemini_client.process_ocr(prompt, processed_image)
        
        # Extract company_id from OCR results
        company_id = data_service.extract_company_id_from_ocr(ocr_results)
        
        # Create ISOLATED classification service for THIS page only (prevents race conditions)
        print(f"    [OCR {page_idx}] Creating isolated classification service for company_id={company_id}", flush=True)
        page_classification_service = ClassificationService(
            mapping_file=CREDENTIAL_MAPPING_FILE,
            fuzzy_threshold=FUZZY_MATCH_THRESHOLD,
            company_id=company_id
        )
        
        # Apply state-level filtering to THIS instance only
        venue_state = data_service.get_venue_state(expense_id)
        if venue_state:
            try:
                with CredentialService() as cred_service:
                    valid_credential_ids = cred_service.get_state_specific_credential_ids(
                        venue_state=venue_state,
                        company_id=company_id
                    )
                
                if valid_credential_ids:
                    page_classification_service.filter_by_state_credentials(
                        valid_credential_ids=valid_credential_ids,
                        company_id=company_id
                    )
                    print(f"    [OCR {page_idx}] State filter applied: {venue_state} ({len(valid_credential_ids)} valid creds)", flush=True)
                else:
                    print(f"    [OCR {page_idx}] [WARN] No valid credentials for state '{venue_state}'", flush=True)
            except Exception as e:
                print(f"    [OCR {page_idx}] [WARN] State filtering failed: {e}", flush=True)
        else:
            print(f"    [OCR {page_idx}] [WARN] No venue state found for expense {expense_id}", flush=True)
        
        classified_results = page_classification_service.classify_ocr_results(ocr_results)
        
        names_found = []
        if not classified_results.empty:
            for _, row in classified_results.iterrows():
                name = row.get('Name', 'Unknown')
                credential = row.get('Credential_Standardized', row.get('Credential_OCR', 'N/A'))
                classification = row.get('Classification', 'Unknown')
                names_found.append(f"{name}, {credential} [{classification}]")
        
        processing_time = time.time() - start_time
        print(f"    [OCR {page_idx}] [OK] Complete: {len(classified_results)} records in {processing_time:.1f}s", flush=True)
        
        return {
            "filename": filename,
            "expense_id": expense_id,
            "names_found": names_found,
            "classified_results": classified_results,
            "processing_time_seconds": round(processing_time, 2),
            "success": True
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        print(f"    [OCR {page_idx}] [FAIL] Failed: {filename} - {str(e)[:100]}", flush=True)
        return {
            "filename": filename,
            "expense_id": None,
            "names_found": [],
            "classified_results": None,
            "processing_time_seconds": round(processing_time, 2),
            "error": str(e),
            "success": False
        }


def process_signin_pages_parallel(signin_pages: List[str], data_service, image_service, 
                                  gemini_client) -> List[Dict]:
    """Process signin pages in parallel."""
    total_pages = len(signin_pages)
    print(f"\n[OCR PROCESSING] Starting parallel OCR on {total_pages} signin pages", flush=True)
    print(f"[OCR PROCESSING] Workers: {MAX_OCR_WORKERS}", flush=True)
    print(f"=" * 80, flush=True)
    
    all_results = []
    completed = 0
    successful = 0
    failed = 0
    overall_start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_OCR_WORKERS) as executor:
        futures = {
            executor.submit(
                process_single_signin_page,
                page_path,
                Path(page_path).name,
                idx + 1,
                data_service,
                image_service,
                gemini_client
            ): idx
            for idx, page_path in enumerate(signin_pages)
        }
        
        print(f"[OCR PROCESSING] All {total_pages} tasks submitted", flush=True)
        print(f"=" * 80, flush=True)
        
        for future in as_completed(futures):
            try:
                result = future.result()
                completed += 1
                
                if result.get('success', False):
                    successful += 1
                else:
                    failed += 1
                
                all_results.append(result)
                
                if completed % 5 == 0 or completed in [1, total_pages]:
                    elapsed = time.time() - overall_start_time
                    avg_time = elapsed / completed
                    eta_seconds = avg_time * (total_pages - completed)
                    progress_pct = (completed / total_pages) * 100
                    
                    print(f"  [PROGRESS] {completed}/{total_pages} pages ({progress_pct:.1f}%) | "
                          f"Success: {successful} | Failed: {failed} | "
                          f"ETA: {eta_seconds/60:.1f}m", flush=True)
                
            except Exception as e:
                completed += 1
                failed += 1
                page_idx = futures[future]
                print(f"  [ERROR] Page {page_idx + 1} failed: {e}", flush=True)
                all_results.append({
                    "filename": signin_pages[page_idx] if page_idx < len(signin_pages) else "Unknown",
                    "error": str(e),
                    "success": False
                })
    
    total_time = time.time() - overall_start_time
    
    print(f"\n{'=' * 80}", flush=True)
    print(f"[OCR COMPLETE] All {total_pages} signin pages processed", flush=True)
    print(f"  [OK] Successful: {successful}/{total_pages} ({successful/total_pages*100:.1f}%)", flush=True)
    print(f"  [FAIL] Failed: {failed}/{total_pages}", flush=True)
    print(f"  ⏱ Total time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)", flush=True)
    print(f"  ⚡ Avg per page: {total_time/total_pages:.1f}s", flush=True)
    print(f"  🚀 Throughput: {(total_pages/total_time)*60:.1f} pages/minute", flush=True)
    print(f"{'=' * 80}\n", flush=True)
    
    return all_results


def main():
    """Main function for batch processing."""
    print("\n" + "=" * 80)
    print("BATCH PROCESSING - OCR FOR ALL FILES IN DATA FOLDER")
    print("=" * 80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data Folder: {DATA_FOLDER}")
    print(f"Concur CSV: {CONCUR_CSV_PATH}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("=" * 80 + "\n")
    
    total_start_time = time.time()
    
    if not os.path.exists(DATA_FOLDER):
        print(f"[ERROR] ERROR: Data folder not found: {DATA_FOLDER}")
        return
    
    if not os.path.exists(CONCUR_CSV_PATH):
        print(f"[ERROR] ERROR: Concur CSV not found: {CONCUR_CSV_PATH}")
        return
    
    # Get all files
    all_files = os.listdir(DATA_FOLDER)
    pdf_files = [f for f in all_files if f.lower().endswith('.pdf')]
    image_files = [f for f in all_files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    print(f"[DISCOVERY] Found files in Data folder:")
    print(f"  - PDF files: {len(pdf_files)}")
    print(f"  - Image files: {len(image_files)}")
    print(f"  - Total: {len(pdf_files) + len(image_files)}")
    
    if not pdf_files and not image_files:
        print("[ERROR] ERROR: No files found in Data folder")
        return
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PAGES_DIR, exist_ok=True)
    check_memory()
    
    # Initialize services
    print("\n[INITIALIZATION] Loading services...")
    print("-" * 80)
    
    try:
        data_service = DataExtractionService(CONCUR_CSV_PATH)
        image_service = ImageProcessingService()
        gemini_client = GeminiClient()
        classification_service = ClassificationService(
            CREDENTIAL_MAPPING_FILE, 
            fuzzy_threshold=FUZZY_MATCH_THRESHOLD
        )
        pdf_processing_service = PDFProcessingService(gemini_client, PAGES_DIR)
        data_service.load_hcp_credentials(CREDENTIAL_MAPPING_FILE)
        
        print("[OK] All services initialized successfully\n")
        
    except Exception as e:
        print(f"[ERROR] ERROR: Failed to initialize services: {e}")
        return
    
    # STAGE 1: Process files
    print(f"\n[STAGE 1/3] PROCESSING FILES")
    print("=" * 80)
    
    all_signin_pages = []
    pdfs_processed = 0
    images_added = 0
    
    # Part 1A: Process PDFs
    if pdf_files:
        print(f"\n[PART 1A] PROCESSING {len(pdf_files)} PDFs IN PARALLEL")
        print(f"Processing in batches of {PDF_BATCH_SIZE_LOCAL} PDFs\n")
        
        num_pdf_batches = (len(pdf_files) + PDF_BATCH_SIZE_LOCAL - 1) // PDF_BATCH_SIZE_LOCAL
        
        for batch_idx in range(num_pdf_batches):
            batch_start = batch_idx * PDF_BATCH_SIZE_LOCAL
            batch_end = min(batch_start + PDF_BATCH_SIZE_LOCAL, len(pdf_files))
            batch_files = pdf_files[batch_start:batch_end]
            
            print(f"\n[PDF BATCH {batch_idx + 1}/{num_pdf_batches}] Processing PDFs {batch_start + 1}-{batch_end} in parallel")
            print("-" * 80)
            
            # Process PDFs in parallel
            def process_single_pdf(filename, pdf_idx):
                try:
                    pdf_path = os.path.join(DATA_FOLDER, filename)
                    print(f"  [{pdf_idx}/{len(pdf_files)}] {filename}", flush=True)
                    
                    results = pdf_processing_service.process_pdf(pdf_path)
                    signin_pages = results.get('signin', [])
                    dinein_pages = results.get('dinein', [])
                    
                    print(f"      [OK] Result: {len(signin_pages)} signin + {len(dinein_pages)} dinein pages", flush=True)
                    return signin_pages, True
                    
                except Exception as e:
                    print(f"      [ERROR] Failed: {e}", flush=True)
                    return [], False
            
            # Submit all PDFs in batch to thread pool
            batch_signin_pages = []
            with ThreadPoolExecutor(max_workers=min(5, len(batch_files))) as executor:
                futures = {
                    executor.submit(process_single_pdf, filename, batch_start + idx + 1): idx
                    for idx, filename in enumerate(batch_files)
                }
                
                for future in as_completed(futures):
                    try:
                        signin_pages, success = future.result()
                        if success:
                            pdfs_processed += 1
                            batch_signin_pages.extend(signin_pages)
                    except Exception as e:
                        print(f"      [WARN] PDF processing error: {e}", flush=True)
            
            all_signin_pages.extend(batch_signin_pages)
            print(f"\n  [BATCH COMPLETE] Processed {len(batch_files)} PDFs, found {len(batch_signin_pages)} signin pages", flush=True)
            
            print(f"\n  [MEMORY] Cleaning up after batch {batch_idx + 1}...", flush=True)
            gc.collect()
            check_memory()
        
        print(f"\n[OK] PDF PROCESSING COMPLETE")
        print(f"  PDFs processed: {pdfs_processed}/{len(pdf_files)}")
        print(f"  Signin pages from PDFs: {len(all_signin_pages)}")
    
    # Part 1B: Add images directly
    if image_files:
        print(f"\n[PART 1B] ADDING {len(image_files)} IMAGE FILES")
        print("-" * 80)
        
        for img_idx, filename in enumerate(image_files, start=1):
            image_path = os.path.join(DATA_FOLDER, filename)
            all_signin_pages.append(image_path)
            images_added += 1
            
            if img_idx % 20 == 0 or img_idx == len(image_files):
                print(f"  Added {img_idx}/{len(image_files)} images", flush=True)
        
        print(f"[OK] All {images_added} images added")
    
    print(f"\n{'=' * 80}")
    print(f"[OK] FILE PROCESSING COMPLETE")
    print(f"  PDFs processed: {pdfs_processed}")
    print(f"  Images added: {images_added}")
    print(f"  Total signin pages: {len(all_signin_pages)}")
    print(f"{'=' * 80}\n")
    
    if not all_signin_pages:
        print("[WARN] WARNING: No signin pages found")
        print(f"\n{'=' * 80}")
        print(f"PROCESSING COMPLETE - NO RESULTS")
        print(f"Total Time: {(time.time() - total_start_time)/60:.1f} minutes")
        print(f"{'=' * 80}\n")
        return
    
    # STAGE 2: Process signin pages with OCR
    print(f"\n[STAGE 2/3] PROCESSING SIGNIN PAGES WITH OCR")
    print("=" * 80)
    print(f"Processing {len(all_signin_pages)} signin pages")
    print(f"Using {MAX_OCR_WORKERS} parallel workers\n")
    
    all_results = process_signin_pages_parallel(
        all_signin_pages,
        data_service,
        image_service,
        gemini_client
    )
    
    # STAGE 3: Group and save results
    print(f"\n[STAGE 3/3] GROUPING AND SAVING RESULTS")
    print("=" * 80)
    
    expense_groups = {}
    for result in all_results:
        if not result.get('success', False) or result.get('classified_results') is None:
            continue
        
        expense_id = result['expense_id']
        if expense_id not in expense_groups:
            expense_groups[expense_id] = []
        expense_groups[expense_id].append(result['classified_results'])
    
    saved_files = []
    for idx, (expense_id, results_list) in enumerate(expense_groups.items(), 1):
        combined_df = pd.concat(results_list, ignore_index=True)
        combined_df = classification_service.remove_duplicate_names(combined_df)
        output_file = classification_service.save_results(combined_df, expense_id)
        saved_files.append(output_file)
        print(f"  [{idx}/{len(expense_groups)}] [OK] Saved {len(combined_df)} records for expense ID: {expense_id}", flush=True)
        print(f"                File: {os.path.basename(output_file)}", flush=True)
    
    # Final statistics
    total_time = time.time() - total_start_time
    successful = sum(1 for r in all_results if r.get('success', False))
    failed = len(all_results) - successful
    
    print(f"\n{'=' * 80}")
    print(f"✅ BATCH PROCESSING COMPLETE")
    print(f"{'=' * 80}")
    print(f"  Files processed:")
    print(f"    - PDFs: {pdfs_processed}")
    print(f"    - Images: {images_added}")
    print(f"    - Total: {pdfs_processed + images_added}")
    print(f"  Signin pages total: {len(all_signin_pages)}")
    print(f"  Signin pages processed: {successful}/{len(all_signin_pages)}")
    print(f"  Failed: {failed}")
    print(f"  Unique expense IDs: {len(expense_groups)}")
    print(f"  Output files saved: {len(saved_files)}")
    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"  Total time: {total_time/60:.1f} minutes ({total_time:.1f} seconds)")
    if pdfs_processed > 0:
        print(f"  Avg time per PDF: {total_time/pdfs_processed:.1f}s")
    if len(all_signin_pages) > 0:
        print(f"  Avg time per signin page: {total_time/len(all_signin_pages):.1f}s")
    print(f"  End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")
    
    check_memory()
    print("\n[OK] All results saved to output folder")
    print("[OK] Processing complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[WARN] Processing interrupted by user")
        print("[OK] Exiting...")
    except Exception as e:
        print(f"\n\n[ERROR] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
