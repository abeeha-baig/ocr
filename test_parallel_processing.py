"""
Test script to verify parallel processing is working correctly.
"""

import requests
import time
from pathlib import Path

def test_api():
    """Test the API with a small batch of PDFs."""
    
    print("=" * 80)
    print("TESTING PARALLEL OCR PROCESSING API")
    print("=" * 80)
    
    # Get PDF files from input directory
    input_dir = Path("app/input")
    pdf_files = list(input_dir.glob("*.pdf"))[:5]  # Test with first 5 PDFs
    
    if not pdf_files:
        print("\n❌ No PDF files found in app/input directory")
        print("Please add some PDF files to test")
        return
    
    print(f"\n✓ Found {len(pdf_files)} PDF files for testing")
    for idx, pdf in enumerate(pdf_files, 1):
        print(f"  {idx}. {pdf.name}")
    
    # Prepare files for upload
    files = [('files', open(pdf, 'rb')) for pdf in pdf_files]
    
    # Submit job
    print("\n" + "=" * 80)
    print("SUBMITTING JOB TO API")
    print("=" * 80)
    
    try:
        response = requests.post('http://127.0.0.1:8080/process-images', files=files)
        
        if response.status_code != 200:
            print(f"\n❌ API Error: {response.status_code}")
            print(response.text)
            return
        
        job_data = response.json()
        job_id = job_data['job_id']
        
        print(f"\n✓ Job submitted successfully!")
        print(f"  Job ID: {job_id}")
        print(f"  Status URL: {job_data['status_url']}")
        print(f"\n{job_data['message']}")
        
        # Poll for status
        print("\n" + "=" * 80)
        print("POLLING JOB STATUS (checking every 10 seconds)")
        print("=" * 80)
        
        last_stage = ""
        last_processed = 0
        
        while True:
            time.sleep(10)
            
            status_response = requests.get(f'http://127.0.0.1:8080/job-status/{job_id}')
            status = status_response.json()
            
            current_stage = status['progress']['current_stage']
            current_processed = status['progress'].get('signin_pages_processed', 0)
            
            # Print update if stage changed or progress increased
            if current_stage != last_stage or current_processed != last_processed:
                print(f"\n[{status['status'].upper()}] Stage: {current_stage}")
                print(f"  PDFs processed: {status['progress']['current']}/{status['progress']['total_pdfs']}")
                print(f"  Signin pages found: {status['progress']['signin_pages_found']}")
                print(f"  Signin pages processed: {current_processed}/{status['progress']['signin_pages_found']}")
                
                last_stage = current_stage
                last_processed = current_processed
            else:
                print(".", end="", flush=True)
            
            # Check if complete
            if status['status'] == 'completed':
                print("\n\n" + "=" * 80)
                print("✅ JOB COMPLETED SUCCESSFULLY!")
                print("=" * 80)
                
                result = status['result']
                print(f"\n📊 RESULTS:")
                print(f"  Total processing time: {result['total_processing_time_minutes']:.1f} minutes")
                print(f"  PDFs processed: {result['pdfs_processed']}")
                print(f"  Signin pages found: {result['signin_pages_found']}")
                print(f"  Signin pages processed: {result['signin_pages_processed']}/{result['signin_pages_found']}")
                print(f"  Success rate: {result['signin_pages_processed']/result['signin_pages_found']*100:.1f}%")
                print(f"  Failed pages: {result['failed']}")
                print(f"  Unique expense IDs: {result['unique_expense_ids']}")
                print(f"\n📁 OUTPUT FILES:")
                for idx, output_file in enumerate(result['output_files'][:5], 1):
                    print(f"  {idx}. {output_file}")
                if len(result['output_files']) > 5:
                    print(f"  ... and {len(result['output_files']) - 5} more files")
                
                break
            
            elif status['status'] == 'failed':
                print("\n\n" + "=" * 80)
                print("❌ JOB FAILED")
                print("=" * 80)
                print(f"\nError: {status['error']}")
                break
    
    finally:
        # Close file handles
        for _, f in files:
            f.close()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    print("\n⚠️  Make sure the API server is running at http://127.0.0.1:8080")
    print("   Start it with: python main.py\n")
    
    input("Press Enter to start the test...")
    
    test_api()
