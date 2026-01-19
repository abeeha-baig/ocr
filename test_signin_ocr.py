"""Simple test script to OCR a signin image."""

from pathlib import Path
from PIL import Image
from app.clients.gemini_client import GeminiClient
from app.constants.config import PAGES_DIR


def test_signin_ocr():
    """OCR one signin image and print results."""
    # Find first signin image
    signin_images = list(Path(PAGES_DIR).glob("*signin*.png"))
    if not signin_images:
        print("No signin images found!")
        return
    
    test_image = signin_images[0]
    print(f"OCR Test - Image: {test_image.name}\n")
    
    # Load image and OCR
    image = Image.open(test_image)
    gemini_client = GeminiClient()
    
    prompt = "OCR the entire text from this signin sheet image. Extract everything you see."
    
    print("Processing...\n")
    result = gemini_client.process_ocr(prompt, image)
    
    print("=" * 80)
    print("OCR RESULTS:")
    print("=" * 80)
    print(result)
    print("=" * 80)


if __name__ == "__main__":
    test_signin_ocr()
