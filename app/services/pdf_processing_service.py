"""PDF processing service for splitting PDFs into pages and classifying them."""

import os
import re
from pathlib import Path
from typing import List, Tuple, Dict
from PIL import Image
import fitz  # PyMuPDF
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.constants.config import MAX_CLASSIFICATION_WORKERS


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
            print(f"⚠️  Error extracting expense ID from {filename}: {e}")
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
            print(f"      ✓ Extracted {len(images)} pages", flush=True)
            return images
            
        except Exception as e:
            print(f"      ❌ Error converting PDF to images: {e}", flush=True)
            raise
    
    def classify_page(self, image: Image.Image, page_name: str) -> str:
        """
        Classify a page as 'signin' or 'dinein' using Gemini 2.0 Flash Lite.
        
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
                # Default to signin if unclear
                print(f"      ⚠️  Unclear classification for {page_name}: '{classification}', defaulting to signin", flush=True)
                return 'signin'
                
        except Exception as e:
            print(f"      ⚠️  Error classifying {page_name}: {e}, defaulting to signin", flush=True)
            return 'signin'
    
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
            print(f"  ❌ Error saving image {filename}: {e}")
            raise
    
    def process_pdf(self, pdf_path: str) -> Dict[str, List[str]]:
        """
        Process a PDF: split into pages, classify, and save with continuous parallel processing.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with 'signin' and 'dinein' page paths
        """
        pdf_filename = Path(pdf_path).name
        
        try:
            # Extract expense ID
            expense_id = self.extract_expense_id_from_filename(pdf_filename)
            print(f"      [Expense ID] {expense_id}", flush=True)
            
            # Convert PDF to images
            page_images = self.pdf_to_images(pdf_path)
            total_pages = len(page_images)
            
            # Classify and save each page in parallel with continuous processing
            results = {
                'signin': [],
                'dinein': [],
                'expense_id': expense_id
            }
            
            print(f"      [Classification] Starting parallel classification of {total_pages} pages...", flush=True)
            print(f"      [Classification] Workers: {self.max_workers} | Submitting all tasks to queue...", flush=True)
            
            completed = 0
            
            def classify_and_save(page_data, page_idx):
                page_name, image = page_data
                classification = self.classify_page(image, page_name)
                saved_path = self.save_page_image(image, page_name, classification)
                return page_idx, page_name, classification, saved_path
            
            # Submit ALL classification tasks at once - executor manages the queue
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(classify_and_save, page_data, idx): idx 
                    for idx, page_data in enumerate(page_images)
                }
                
                # Process results as they complete (continuous parallel processing)
                signin_count = 0
                dinein_count = 0
                for future in as_completed(futures):
                    try:
                        page_idx, page_name, classification, saved_path = future.result(timeout=60)
                        results[classification].append(saved_path)
                        completed += 1
                        
                        # Track counts
                        if classification == 'signin':
                            signin_count += 1
                        else:
                            dinein_count += 1
                        
                        # Log progress
                        print(f"        [{completed}/{total_pages}] ✓ Page {page_idx + 1}: {classification} (signin: {signin_count}, dinein: {dinein_count})", flush=True)
                        
                    except Exception as e:
                        completed += 1
                        page_idx = futures[future]
                        print(f"        [{completed}/{total_pages}] ✗ Page {page_idx + 1}: Error - {e}", flush=True)
            print(f"      [Classification Complete] Signin: {signin_count} | Dinein: {dinein_count}", flush=True)
            
            return results
            
        except Exception as e:
            print(f"      ❌ Error processing PDF {pdf_filename}: {e}", flush=True)
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
            print("⚠️  No PDF files found in input directory")
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
                print(f"  ⚠️  Skipping {pdf_path.name} due to error: {e}\n")
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
