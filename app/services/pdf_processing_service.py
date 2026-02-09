"""PDF processing service for splitting PDFs into pages and classifying them."""

import os
import re
from pathlib import Path
from typing import List, Tuple, Dict
from PIL import Image
import fitz  # PyMuPDF
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytesseract
from rapidfuzz import fuzz
from app.constants.config import MAX_CLASSIFICATION_WORKERS, MAX_CLASSIFICATION_BATCH_SIZE, TESSERACT_PATH

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


class PDFProcessingService:
    """Service for processing PDFs: splitting into pages and classifying."""
    
    # Maximum dimensions to avoid WebP encoding errors (16383 pixel limit)
    MAX_IMAGE_DIMENSION = 4096  # Safe limit well below 16383
    
    def __init__(self, gemini_client, pages_dir: str):
        """
        Initialize PDF processing service.
        
        Args:
            gemini_client: GeminiClient instance for classification
            pages_dir: Directory to save extracted pages
        """
        self.gemini_client = gemini_client
        self.pages_dir = pages_dir
        self.classification_model = genai.GenerativeModel("gemini-2.5-flash-lite")
        self.max_workers = MAX_CLASSIFICATION_WORKERS
        
        # Ensure pages directory exists
        os.makedirs(self.pages_dir, exist_ok=True)
        
        print(f"[PDF SERVICE] Initialized - Max classification workers: {self.max_workers}", flush=True)
    
    def resize_image_if_needed(self, image: Image.Image) -> Image.Image:
        """
        Resize image if it exceeds maximum dimensions while maintaining aspect ratio and quality.
        
        Args:
            image: PIL Image to resize
            
        Returns:
            Resized PIL Image (or original if no resize needed)
        """
        width, height = image.size
        max_dim = max(width, height)
        
        if max_dim <= self.MAX_IMAGE_DIMENSION:
            return image
        
        # Calculate new dimensions maintaining aspect ratio
        scale_factor = self.MAX_IMAGE_DIMENSION / max_dim
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        # Use LANCZOS for high-quality downsampling
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return resized
    
    def extract_expense_id_from_filename(self, filename: str) -> str:
        """
        Extract expense ID from PDF filename.
        
        The expense ID is the part after the second underscore.
        Example: "1F606C186AB64BE5ADA9_HCP Spend_gWin$pt8sc3zEgHtcCnH3jZn0yCPcLjvlyfg_..."
        Returns: "gWin$pt8sc3zEgHtcCnH3jZn0yCPcLjvlyfg"
        
        Args:
            filename: PDF filename
            
        Returns:
            Expense ID string
        """
        try:
            # Split by underscore and get the third part (index 2)
            parts = filename.split('_')
            if len(parts) >= 3:
                expense_id = parts[2]
                return expense_id
            else:
                raise ValueError(f"Filename doesn't have expected format: {filename}")
        except Exception as e:
            print(f"[WARN] Error extracting expense ID from {filename}: {e}")
            # Fallback: use filename without extension
            return Path(filename).stem
    
    def pdf_to_images(self, pdf_path: str) -> List[Tuple[str, Image.Image]]:
        """
        Convert PDF pages to images.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of tuples (page_name, PIL Image)
        """
        try:
            pdf_filename = Path(pdf_path).stem
            doc = fitz.open(pdf_path)
            images = []
            
            print(f"      [PDF→Images] Converting {len(doc)} pages...", flush=True)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Convert page to image (300 DPI for good quality)
                mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Resize if needed to avoid encoding errors
                img = self.resize_image_if_needed(img)
                
                # Generate page name
                page_name = f"{pdf_filename}_page_{page_num + 1}"
                images.append((page_name, img))
            
            doc.close()
            print(f"      [OK] Extracted {len(images)} pages", flush=True)
            return images
            
        except Exception as e:
            print(f"      [ERROR] Error converting PDF to images: {e}", flush=True)
            raise
    
    def classify_page_with_tesseract(self, image: Image.Image, page_name: str) -> str:
        """
        Classify a page as 'signin' or 'dinein' using Tesseract OCR with fuzzy keyword matching.
        
        A page is classified as 'signin' if it contains ALL three keywords (with fuzzy matching):
        - "name" (or variants like "names")
        - "signature" (or variants like "signatures")  
        - "credential" (or variants like "credentials")
        
        Uses rapidfuzz with 85% similarity threshold to handle OCR variations.
        
        Args:
            image: PIL Image of the page
            page_name: Name of the page for logging
            
        Returns:
            'signin' or 'dinein'
        """
        try:
            # Perform OCR on the image
            ocr_text = pytesseract.image_to_string(image).lower()
            
            # Split text into words for fuzzy matching
            ocr_words = ocr_text.split()
            
            # Required keywords with fuzzy matching (85% threshold)
            required_keywords = ['name', 'signature', 'credential']
            fuzzy_threshold = 85
            
            # Check if each keyword has a fuzzy match in the OCR text
            def has_fuzzy_match(keyword: str) -> bool:
                """Check if keyword has a fuzzy match in any OCR word."""
                for word in ocr_words:
                    if fuzz.ratio(keyword, word) >= fuzzy_threshold:
                        return True
                return False
            
            # Check if ALL required keywords are present (with fuzzy matching)
            has_all_keywords = all(has_fuzzy_match(keyword) for keyword in required_keywords)
            
            if has_all_keywords:
                return 'signin'
            else:
                return 'dinein'
                
        except Exception as e:
            print(f"      [WARN] Error in Tesseract classification for {page_name}: {e}, defaulting to dinein", flush=True)
            return 'dinein'
    
    def classify_page(self, image: Image.Image, page_name: str) -> str:
        """
        Classify a page as 'signin' or 'dinein' using Gemini 2.5 Flash Lite (fallback).
        
        Args:
            image: PIL Image of the page
            page_name: Name of the page for logging
            
        Returns:
            'signin' or 'dinein'
        """
        try:
            prompt = """You are a page classifier. Analyze this image and determine if it is a SIGNIN page or a DINEIN page.

SIGNIN pages contain:
- Keywords like "name", "signature", "credential"
- A list or table of names with signatures
- Credential information (MD, RN, NP, etc.)

DINEIN pages contain:
- Everything else that is not a signin page
- Menu items, food descriptions, receipts
- Prices, amounts, or invoices
- Restaurant or catering information

Respond with ONLY ONE WORD:
- "signin" if this is a signin page
- "dinein" if this is a dinein page

Answer:"""
            
            response = self.classification_model.generate_content([prompt, image])
            classification = response.text.strip().lower()
            
            # Validate response
            if 'signin' in classification:
                return 'signin'
            elif 'dinein' in classification:
                return 'dinein'
            else:
                # Default to dinein if unclear
                print(f"      [WARN] Unclear LLM classification for {page_name}: '{classification}', defaulting to dinein", flush=True)
                return 'dinein'
                
        except Exception as e:
            print(f"      [WARN] Error in LLM classification for {page_name}: {e}, defaulting to dinein", flush=True)
            return 'dinein'
    
    def classify_pages_batch(self, images: List[Tuple[Image.Image, str]]) -> List[str]:
        """
        Classify multiple pages in a single API call using Gemini 2.5 Flash Lite.
        This reduces API calls significantly (e.g., 20 pages = 2 calls instead of 20).
        
        Args:
            images: List of tuples (PIL Image, page_name)
            
        Returns:
            List of classifications ('signin' or 'dinein') in same order as input
        """
        try:
            batch_size = len(images)
            
            # Build prompt for batch classification
            prompt = f"""You are a page classifier. Analyze these {batch_size} images and classify each as SIGNIN or DINEIN.

SIGNIN pages contain:
- Keywords like "name", "signature", "credential"
- A list or table of names with signatures
- Credential information (MD, RN, NP, etc.)

DINEIN pages contain:
- Everything else that is not a signin page
- Menu items, food descriptions, receipts
- Prices, amounts, or invoices
- Restaurant or catering information

Respond with ONLY a comma-separated list of classifications in order:
Example: signin,dinein,dinein,signin,dinein

Classifications:"""
            
            # Prepare content: prompt followed by all images
            content_parts = [prompt] + [img for img, _ in images]
            
            response = self.classification_model.generate_content(content_parts)
            classifications_text = response.text.strip().lower()
            
            # Parse response (comma-separated values)
            classifications = [c.strip() for c in classifications_text.split(',')]
            
            # Validate and clean classifications
            valid_classifications = []
            for i, classification in enumerate(classifications):
                if 'signin' in classification:
                    valid_classifications.append('signin')
                elif 'dinein' in classification:
                    valid_classifications.append('dinein')
                else:
                    # Default to dinein if unclear
                    page_name = images[i][1] if i < len(images) else f"page_{i}"
                    print(f"      [WARN] Unclear batch classification for {page_name}: '{classification}', defaulting to dinein", flush=True)
                    valid_classifications.append('dinein')
            
            # Ensure we have exactly the right number of classifications
            while len(valid_classifications) < batch_size:
                valid_classifications.append('dinein')
            
            return valid_classifications[:batch_size]
                
        except Exception as e:
            print(f"      [WARN] Error in batch classification: {e}, defaulting all to dinein", flush=True)
            return ['dinein'] * len(images)
    
    def save_page_image(self, image: Image.Image, page_name: str, classification: str) -> str:
        """
        Save page image with classification in filename.
        
        Args:
            image: PIL Image
            page_name: Base name for the page
            classification: 'signin' or 'dinein'
            
        Returns:
            Path to saved image
        """
        filename = f"{page_name}_{classification}.png"
        filepath = os.path.join(self.pages_dir, filename)
        
        try:
            image.save(filepath, "PNG")
            return filepath
        except Exception as e:
            print(f"  [ERROR] Error saving image {filename}: {e}")
            raise
    
    def check_if_already_split(self, pdf_path: str) -> Dict[str, List[str]]:
        """
        Check if PDF has already been split by looking for existing page images.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with existing 'signin' and 'dinein' page paths, or None if not found
        """
        pdf_filename = Path(pdf_path).stem
        
        # Look for page images with this PDF name
        signin_pages = list(Path(self.pages_dir).glob(f"{pdf_filename}_page_*_signin.png"))
        dinein_pages = list(Path(self.pages_dir).glob(f"{pdf_filename}_page_*_dinein.png"))
        
        if signin_pages or dinein_pages:
            print(f"      [OK] Found existing split pages ({len(signin_pages)} signin, {len(dinein_pages)} dinein) - skipping split", flush=True)
            return {
                'signin': [str(p) for p in signin_pages],
                'dinein': [str(p) for p in dinein_pages],
                'expense_id': self.extract_expense_id_from_filename(Path(pdf_path).name)
            }
        
        return None
    
    def process_pdf(self, pdf_path: str, skip_split_check: bool = False) -> Dict[str, List[str]]:
        """
        Process a PDF: split into pages, classify with Tesseract, fallback to LLM if needed.
        
        Strategy:
        1. Check if already split (unless skip_split_check=True)
        2. Split PDF into pages
        3. Classify ALL pages using Tesseract (parallel)
        4. If NO signin pages found, reclassify ALL pages using LLM (parallel fallback)
        5. Save pages with classification
        
        Args:
            pdf_path: Path to PDF file
            skip_split_check: If True, force re-splitting even if pages exist
            
        Returns:
            Dictionary with 'signin' and 'dinein' page paths
        """
        pdf_filename = Path(pdf_path).name
        
        try:
            # Extract expense ID
            expense_id = self.extract_expense_id_from_filename(pdf_filename)
            print(f"      [Expense ID] {expense_id}", flush=True)
            
            # Check if already split
            if not skip_split_check:
                existing_results = self.check_if_already_split(pdf_path)
                if existing_results:
                    return existing_results
            
            # Convert PDF to images
            page_images = self.pdf_to_images(pdf_path)
            total_pages = len(page_images)
            
            # STEP 1: Classify ALL pages using Tesseract (parallel)
            print(f"      [Tesseract Classification] Classifying {total_pages} pages in parallel...", flush=True)
            
            tesseract_results = []
            completed = 0
            
            def classify_with_tesseract(page_data, page_idx):
                page_name, image = page_data
                classification = self.classify_page_with_tesseract(image, page_name)
                return page_idx, page_name, image, classification
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(classify_with_tesseract, page_data, idx): idx 
                    for idx, page_data in enumerate(page_images)
                }
                
                signin_count = 0
                dinein_count = 0
                for future in as_completed(futures):
                    try:
                        page_idx, page_name, image, classification = future.result(timeout=60)
                        tesseract_results.append((page_idx, page_name, image, classification))
                        completed += 1
                        
                        if classification == 'signin':
                            signin_count += 1
                        else:
                            dinein_count += 1
                        
                        if completed % 5 == 0 or completed == total_pages:
                            print(f"        [{completed}/{total_pages}] Tesseract: signin={signin_count}, dinein={dinein_count}", flush=True)
                        
                    except Exception as e:
                        completed += 1
                        page_idx = futures[future]
                        print(f"        [{completed}/{total_pages}] [FAIL] Tesseract error on page {page_idx + 1}: {e}", flush=True)
            
            print(f"      [Tesseract Complete] Signin: {signin_count} | Dinein: {dinein_count}", flush=True)
            
            # STEP 2: If NO signin pages found, use LLM fallback with BATCH CLASSIFICATION
            final_results = []
            if signin_count == 0:
                print(f"      [LLM Fallback] No signin pages found with Tesseract - reclassifying ALL pages with BATCH LLM...", flush=True)
                
                # Sort results by page index
                sorted_results = sorted(tesseract_results, key=lambda x: x[0])
                
                # Process in batches to reduce API calls
                batch_size = MAX_CLASSIFICATION_BATCH_SIZE
                num_batches = (len(sorted_results) + batch_size - 1) // batch_size
                print(f"        Batch size: {batch_size} pages per API call | Total batches: {num_batches}", flush=True)
                
                signin_count = 0
                dinein_count = 0
                
                for batch_idx in range(num_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(start_idx + batch_size, len(sorted_results))
                    batch_results = sorted_results[start_idx:end_idx]
                    
                    # Prepare images for batch classification
                    batch_images = [(image, page_name) for _, page_name, image, _ in batch_results]
                    
                    # Classify entire batch in one API call
                    try:
                        batch_classifications = self.classify_pages_batch(batch_images)
                        
                        # Store results
                        for i, classification in enumerate(batch_classifications):
                            page_idx, page_name, image, _ = batch_results[i]
                            final_results.append((page_idx, page_name, image, classification))
                            
                            if classification == 'signin':
                                signin_count += 1
                            else:
                                dinein_count += 1
                        
                        print(f"        [Batch {batch_idx+1}/{num_batches}] Processed {len(batch_classifications)} pages | signin={signin_count}, dinein={dinein_count}", flush=True)
                    
                    except Exception as e:
                        print(f"        [Batch {batch_idx+1}/{num_batches}] [FAIL] Error: {e} - defaulting to dinein", flush=True)
                        # Fallback: mark all pages in batch as dinein
                        for page_idx, page_name, image, _ in batch_results:
                            final_results.append((page_idx, page_name, image, 'dinein'))
                            dinein_count += 1
                
                print(f"      [LLM Complete] Signin: {signin_count} | Dinein: {dinein_count} | API calls saved: {len(sorted_results) - num_batches}", flush=True)
            else:
                # Use Tesseract results
                final_results = tesseract_results
            
            # STEP 3: Save all pages with classification
            print(f"      [Saving] Saving {len(final_results)} classified pages...", flush=True)
            
            results = {
                'signin': [],
                'dinein': [],
                'expense_id': expense_id
            }
            
            for page_idx, page_name, image, classification in sorted(final_results, key=lambda x: x[0]):
                saved_path = self.save_page_image(image, page_name, classification)
                results[classification].append(saved_path)
            
            print(f"      [OK] Saved: {len(results['signin'])} signin, {len(results['dinein'])} dinein", flush=True)
            
            return results
            
        except Exception as e:
            print(f"      [ERROR] Error processing PDF {pdf_filename}: {e}", flush=True)
            raise
    
    def process_all_pdfs(self, input_dir: str) -> Dict[str, List[str]]:
        """
        Process all PDFs in the input directory.
        
        Args:
            input_dir: Directory containing PDF files
            
        Returns:
            Dictionary mapping expense IDs to signin page paths
        """
        print(f"\n{'='*60}")
        print(f"PDF PROCESSING PIPELINE")
        print(f"{'='*60}")
        print(f"Input directory: {input_dir}\n")
        
        # Find all PDF files
        pdf_files = list(Path(input_dir).glob("*.pdf"))
        
        if not pdf_files:
            print("[WARN] No PDF files found in input directory")
            return {}
        
        print(f"Found {len(pdf_files)} PDF file(s)\n")
        
        # Track results by expense ID
        all_signin_pages = {}
        all_results = []
        
        for idx, pdf_path in enumerate(pdf_files, 1):
            print(f"[{idx}/{len(pdf_files)}]", end=" ")
            try:
                results = self.process_pdf(str(pdf_path))
                expense_id = results['expense_id']
                
                # Group signin pages by expense ID
                if expense_id not in all_signin_pages:
                    all_signin_pages[expense_id] = []
                all_signin_pages[expense_id].extend(results['signin'])
                
                all_results.append({
                    'pdf': pdf_path.name,
                    'expense_id': expense_id,
                    'signin_count': len(results['signin']),
                    'dinein_count': len(results['dinein'])
                })
                
            except Exception as e:
                print(f"  [WARN] Skipping {pdf_path.name} due to error: {e}\n")
                continue
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"PDF PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Total PDFs processed: {len(all_results)}")
        print(f"Unique expense IDs: {len(all_signin_pages)}")
        print(f"Total signin pages: {sum(len(pages) for pages in all_signin_pages.values())}")
        print(f"{'='*60}\n")
        
        return all_signin_pages
