# OCR Processing API - Usage Guide for 50 PDFs

## 🎯 Overview

Your application can now process up to **50 PDFs** in a single API call with:
- ✅ **Async job queue** - No HTTP timeout issues
- ✅ **Comprehensive logging** - Track progress at every step
- ✅ **Memory management** - Process PDFs in batches to avoid crashes
- ✅ **API rate limiting** - Stay under Gemini API limits
- ✅ **Progress tracking** - Check status anytime during processing

## 🚀 How to Use

### 1. Start the Server

```bash
# Make sure you're in the project directory and env is activated
cd c:\Users\abeeha.baig\OneDrive - Qordata\Desktop\ocr-2
conda activate test-env

# Start the server
python main.py
```

Server will start at: `http://127.0.0.1:8080`

### 2. Submit PDFs for Processing

**Endpoint:** `POST /process-images`

```python
import requests
import time

# Prepare your PDF files
files = [
    ('files', open('pdf1.pdf', 'rb')),
    ('files', open('pdf2.pdf', 'rb')),
    # ... up to 50 PDFs
]

# Submit the job
response = requests.post('http://127.0.0.1:8080/process-images', files=files)
job_data = response.json()

print(f"Job ID: {job_data['job_id']}")
print(f"Status URL: {job_data['status_url']}")
```

**Response (returns immediately):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Processing started for 50 PDF(s)",
  "status_url": "/job-status/550e8400-e29b-41d4-a716-446655440000",
  "instructions": "Poll the status_url to check progress. Processing may take 30-60 minutes for 50 PDFs."
}
```

### 3. Check Job Status

**Endpoint:** `GET /job-status/{job_id}`

```python
# Poll for status (check every 30 seconds)
job_id = job_data['job_id']

while True:
    status_response = requests.get(f'http://127.0.0.1:8080/job-status/{job_id}')
    status = status_response.json()
    
    print(f"Status: {status['status']}")
    print(f"Progress: {status['progress']}")
    
    if status['status'] in ['completed', 'failed']:
        break
    
    time.sleep(30)  # Wait 30 seconds before checking again

# Get final results
if status['status'] == 'completed':
    print("Results:", status['result'])
else:
    print("Error:", status['error'])
```

**Status Response (during processing):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": {
    "current": 15,
    "total_pdfs": 50,
    "signin_pages_found": 45,
    "signin_pages_processed": 20,
    "current_stage": "ocr_processing"
  },
  "created_at": "2026-01-27T10:30:00",
  "started_at": "2026-01-27T10:30:05",
  "completed_at": null,
  "result": null,
  "error": null
}
```

**Status Response (completed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": {
    "current": 50,
    "total_pdfs": 50,
    "signin_pages_found": 120,
    "signin_pages_processed": 115,
    "current_stage": "completed"
  },
  "created_at": "2026-01-27T10:30:00",
  "started_at": "2026-01-27T10:30:05",
  "completed_at": "2026-01-27T11:15:23",
  "result": {
    "total_processing_time_seconds": 2718,
    "total_processing_time_minutes": 45.3,
    "pdfs_processed": 50,
    "signin_pages_found": 120,
    "signin_pages_processed": 115,
    "failed": 5,
    "unique_expense_ids": 50,
    "output_files": ["path/to/output1.csv", "path/to/output2.csv", ...],
    "message": "Processing complete! 115/120 pages processed successfully."
  },
  "error": null
}
```

## 📊 Processing Stages

The job goes through these stages (visible in `progress.current_stage`):

1. **queued** - Job created, waiting to start
2. **initializing** - Setting up temporary directories
3. **uploading** - Saving PDF files to temp storage
4. **extracting_pages** - Converting PDFs to images
5. **ocr_processing** - Running OCR on signin pages
6. **saving_results** - Combining and saving results
7. **completed** - Job finished successfully

## 🖥️ Server Console Logs

When processing, you'll see detailed logs like:

```
================================================================================
[API REQUEST] Received 50 PDF file(s) for processing
================================================================================

[VALIDATION] Checking file types...
✓ All files are valid PDFs

[JOB CREATED] Job ID: 550e8400
[JOB CREATED] Total PDFs: 50
[JOB CREATED] Status URL: /job-status/550e8400-e29b-41d4-a716-446655440000

[BACKGROUND TASK] Processing started in background
================================================================================

================================================================================
[JOB 550e8400] STARTING BACKGROUND PROCESSING
================================================================================

[SETUP] Created temporary directory: C:\Users\...\Temp\tmp1234
[MEMORY] Current usage: 45.2% (8.75 GB available)

[STAGE 1/4] UPLOADING PDFs TO TEMPORARY STORAGE
================================================================================
  [1/50] ✓ Saved: file1.pdf (2.34 MB)
  [2/50] ✓ Saved: file2.pdf (1.87 MB)
  ...
✓ All 50 PDF files saved

[STAGE 2/4] EXTRACTING AND CLASSIFYING PAGES
================================================================================
Processing in sub-batches of 10 PDFs to manage memory

[PDF BATCH 1/5] Processing PDFs 1-10
--------------------------------------------------------------------------------

  [1/50] file1.pdf
      [Expense ID] gWin$pt8sc3zEgHtcCnH3jZn0yCPcLjvlyfg
      [PDF→Images] Converting 6 pages...
      ✓ Extracted 6 pages
      [Classification] Using 5 parallel workers...
      ✓ Extracted: 2 signin + 4 dinein pages

  [MEMORY] Cleaning up after batch 1...
  [MEMORY] Current usage: 52.3% (7.61 GB available)

[STAGE 3/4] PROCESSING SIGNIN PAGES WITH OCR
================================================================================
Processing 120 signin pages in batches of 20
Using 8 parallel workers per batch

[OCR BATCH 1/6] Processing signin pages 1-20
--------------------------------------------------------------------------------
  ✓ Batch 1 complete:
      Processed: 20 pages
      Successful: 19
      Failed: 1
      Time: 156.3s (avg 7.8s per page)
      Pausing 2 seconds before next batch...

[STAGE 4/4] COMBINING AND SAVING RESULTS
================================================================================
  [1/50] ✓ Saved 15 records for expense ID: gWin$pt8...
  [2/50] ✓ Saved 12 records for expense ID: hXin$qt9...

================================================================================
✅ JOB COMPLETE - Job ID: 550e8400
================================================================================
  PDFs processed: 50
  Signin pages found: 120
  Signin pages processed: 115/120
  Failed: 5
  Unique expense IDs: 50
  Output files saved: 50
  Total time: 45.3 minutes (2718.0 seconds)
  Avg time per PDF: 54.4 seconds
================================================================================
```

## ⚙️ Configuration

Key settings in `app/constants/config.py`:

```python
BATCH_SIZE = 20                    # Signin pages per batch
MAX_WORKERS_PER_BATCH = 8          # Parallel OCR workers
PDF_BATCH_SIZE = 10                # PDFs processed together
MAX_CLASSIFICATION_WORKERS = 5      # Page classification workers
GEMINI_API_TIMEOUT = 120           # 2 minutes per API call
JOB_TIMEOUT = 3600                 # 1 hour total job timeout
MAX_PDFS_PER_REQUEST = 50          # Maximum PDFs per request
```

## 🔧 Health Check

**Endpoint:** `GET /health`

```bash
curl http://127.0.0.1:8080/health
```

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "data_service": true,
    "image_service": true,
    "gemini_client": true,
    "classification_service": true
  },
  "memory": {
    "percent": 45.2,
    "available_gb": 8.75,
    "total_gb": 16.0
  }
}
```

## 📈 Expected Performance

### For 50 PDFs (5-6 pages each, ~40% signin pages):

- **Total Pages:** ~275 pages
- **Signin Pages:** ~110 pages
- **API Calls:** ~385 calls (275 classification + 110 OCR)
- **Processing Time:** 40-60 minutes
- **Memory Usage:** 8-10 GB peak

### Breakdown by Stage:
1. Upload: 1-2 minutes
2. PDF extraction & classification: 25-30 minutes
3. OCR processing: 15-20 minutes
4. Saving results: 1-2 minutes

## ⚠️ Important Notes

1. **Memory Requirements:** Recommended 16GB RAM for 50 PDFs
2. **API Limits:** Using Gemini Paid Tier (1000 RPM) recommended
3. **Timeout:** Client must not timeout while polling status
4. **Concurrent Jobs:** Can run multiple jobs if memory allows
5. **Error Recovery:** Failed pages don't stop the entire job

## 🐛 Troubleshooting

### Memory Error (503 Response)
```json
{
  "detail": "Server memory critically low (87% used). Please try again later."
}
```
**Solution:** Wait for current jobs to complete, or reduce `PDF_BATCH_SIZE`

### Rate Limit Error
If you see `[GEMINI API] ⚠️ Rate limit hit` in logs:
- System automatically waits and retries
- Consider reducing `MAX_WORKERS_PER_BATCH`

### Job Failed
Check the error in job status response:
```python
status = requests.get(f'http://127.0.0.1:8080/job-status/{job_id}').json()
print(status['error'])  # See what went wrong
```

## 🎁 Bonus: Batch Processing Script

```python
import requests
import time
from pathlib import Path

def process_pdfs_async(pdf_directory, batch_size=50):
    """Process all PDFs in a directory in batches."""
    pdf_files = list(Path(pdf_directory).glob("*.pdf"))
    
    print(f"Found {len(pdf_files)} PDFs")
    
    # Process in batches of 50
    for i in range(0, len(pdf_files), batch_size):
        batch = pdf_files[i:i+batch_size]
        
        print(f"\nSubmitting batch {i//batch_size + 1} ({len(batch)} PDFs)...")
        
        files = [('files', open(pdf, 'rb')) for pdf in batch]
        response = requests.post('http://127.0.0.1:8080/process-images', files=files)
        
        if response.status_code == 200:
            job = response.json()
            print(f"Job ID: {job['job_id']}")
            
            # Poll until complete
            while True:
                status = requests.get(f"http://127.0.0.1:8080{job['status_url']}").json()
                
                if status['status'] == 'completed':
                    print(f"✅ Batch complete!")
                    print(f"   Results: {status['result']['message']}")
                    break
                elif status['status'] == 'failed':
                    print(f"❌ Batch failed: {status['error']}")
                    break
                else:
                    progress = status['progress']
                    print(f"   Progress: {progress['signin_pages_processed']}/{progress['signin_pages_found']} pages", end='\r')
                    time.sleep(30)
        
        # Close file handles
        for _, f in files:
            f.close()

# Usage
process_pdfs_async("path/to/pdf/directory")
```

## 📞 Support

For issues or questions, check the server console logs for detailed error messages.
