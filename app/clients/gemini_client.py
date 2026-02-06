"""Gemini API client for OCR processing."""

import os
import time
from functools import wraps
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
from app.constants.config import GEMINI_MODEL_NAME


def rate_limited(max_per_minute=60):
    """
    Decorator to rate limit API calls.
    
    Args:
        max_per_minute: Maximum API calls allowed per minute
    """
    min_interval = 60.0 / max_per_minute
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator


class GeminiClient:
    """Client for interacting with Google Gemini API."""
    
    def __init__(self, model_name=None):
        """
        Initialize Gemini client.
        
        Args:
            model_name: Name of the Gemini model to use (defaults to config value)
        """
        load_dotenv()
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = model_name or GEMINI_MODEL_NAME
        self.model = genai.GenerativeModel(self.model_name)
        
        # Track API calls for monitoring
        self.request_count = 0
        self.start_time = time.time()
        self.last_log_time = time.time()
        self.classification_count = 0
        self.ocr_count = 0
        
        print(f"[GEMINI CLIENT] Initialized with model: {model_name}", flush=True)
    
    @rate_limited(max_per_minute=45)  # Stay under API limits (15 free, 60 paid)
    def generate_content(self, prompt, image=None):
        """
        Generate content using Gemini model with rate limiting and logging.
        
        Args:
            prompt: Text prompt for the model
            image: Optional PIL Image object
            
        Returns:
            Response text from the model
        """
        self.request_count += 1
        
        # Log API rate every 10 requests
        if self.request_count % 10 == 0:
            elapsed = time.time() - self.start_time
            rate = self.request_count / (elapsed / 60)
            print(f"[GEMINI API] Rate: {rate:.1f} requests/min (Total: {self.request_count} calls)", flush=True)
        
        try:
            start_time = time.time()
            
            if image:
                response = self.model.generate_content([prompt, image])
            else:
                response = self.model.generate_content(prompt)
            
            api_time = time.time() - start_time
            
            # Log slow API calls
            if api_time > 10:
                print(f"[GEMINI API] ⚠️  Slow API call: {api_time:.1f}s", flush=True)
            
            return response.text or ""
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle rate limiting errors
            if "rate" in error_msg or "quota" in error_msg:
                print(f"[GEMINI API] ⚠️  Rate limit hit, waiting 10 seconds...", flush=True)
                time.sleep(10)
                return self.generate_content(prompt, image)  # Retry
            
            # Handle timeout errors
            elif "timeout" in error_msg:
                print(f"[GEMINI API] ⚠️  Timeout error, retrying...", flush=True)
                if image:
                    # Try with compressed image
                    compressed = self._compress_image(image)
                    return self.generate_content(prompt, compressed)
                raise
            
            else:
                print(f"[GEMINI API] ❌ Error: {e}", flush=True)
                raise
    
    def _compress_image(self, image: Image.Image) -> Image.Image:
        """
        Reduce image size for retry after timeout.
        
        Args:
            image: PIL Image to compress
            
        Returns:
            Compressed PIL Image
        """
        max_size = 2048
        width, height = image.size
        
        if max(width, height) <= max_size:
            return image
        
        # Calculate new dimensions
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        print(f"[GEMINI API] Compressed image from {width}x{height} to {new_width}x{new_height}", flush=True)
        return resized
    
    def process_ocr(self, prompt, image):
        """
        Process OCR on an image.
        
        Args:
            prompt: OCR instruction prompt
            image: PIL Image object
            
        Returns:
            Extracted text from image
        """
        self.ocr_count += 1
        
        # Log OCR rate every 10 calls
        if self.ocr_count % 10 == 0:
            elapsed = time.time() - self.start_time
            rate = self.ocr_count / (elapsed / 60)
            print(f"      [GEMINI OCR] Rate: {rate:.1f} OCR/min (Total OCR calls: {self.ocr_count})", flush=True)
        
        return self.generate_content(prompt, image)
