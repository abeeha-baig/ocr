"""Test script for FastAPI OCR service."""

import requests
from pathlib import Path

# API endpoint
API_URL = "http://localhost:8080"


def test_health():
    """Test health check endpoint."""
    response = requests.get(f"{API_URL}/health")
    print("Health Check:")
    print(response.json())
    print()


def test_process_images(image_paths):
    """
    Test image processing endpoint.
    
    Args:
        image_paths: List of image file paths to process
    """
    files = []
    
    # Prepare files for upload
    for image_path in image_paths:
        path = Path(image_path)
        if not path.exists():
            print(f"⚠️ File not found: {image_path}")
            continue
        files.append(
            ('files', (path.name, open(image_path, 'rb'), 'image/jpeg'))
        )
    
    if not files:
        print("❌ No valid files to process")
        return
    
    print(f"Uploading {len(files)} image(s)...")
    
    # Send POST request
    response = requests.post(f"{API_URL}/process-images", files=files)
    
    # Close file handles
    for _, (_, file_obj, _) in files:
        file_obj.close()
    
    # Print results
    if response.status_code == 200:
        result = response.json()
        print("\n" + "="*60)
        print("PROCESSING RESULTS:")
        print("="*60)
        print(f"\nSummary:")
        print(f"  Total: {result['summary']['total']}")
        print(f"  Successful: {result['summary']['successful']}")
        print(f"  Failed: {result['summary']['failed']}")
        
        print(f"\nDetails:")
        for idx, res in enumerate(result['results'], 1):
            print(f"\n{idx}. {res['filename']}")
            print(f"   Status: {res['status']}")
            if res['status'] == 'success':
                print(f"   Expense ID: {res['expense_id']}")
                print(f"   HCP Count: {res['hcp_count']}")
                print(f"   Output File: {res.get('output_file', 'N/A')}")
            else:
                print(f"   Error: {res.get('error', 'Unknown error')}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    # Test health endpoint
    test_health()
    
    # Example: Test with image files
    # Replace these paths with actual image file paths
    image_files = [
        r"app\input\your_image_1.jpg",
        r"app\input\your_image_2.jpg",
    ]
    
    # Uncomment to test
    # test_process_images(image_files)
    
    print("\nTo test image processing, update the image_files list in test_api.py")
