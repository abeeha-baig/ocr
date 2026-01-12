"""Gemini API client for OCR processing."""

import os
import google.generativeai as genai
from dotenv import load_dotenv


class GeminiClient:
    """Client for interacting with Google Gemini API."""
    
    def __init__(self, model_name="gemini-2.5-flash"):
        """
        Initialize Gemini client.
        
        Args:
            model_name: Name of the Gemini model to use
        """
        load_dotenv()
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)
    
    def generate_content(self, prompt, image=None):
        """
        Generate content using Gemini model.
        
        Args:
            prompt: Text prompt for the model
            image: Optional PIL Image object
            
        Returns:
            Response text from the model
        """
        if image:
            response = self.model.generate_content([prompt, image])
        else:
            response = self.model.generate_content(prompt)
        
        return response.text or ""
    
    def process_ocr(self, prompt, image):
        """
        Process OCR on an image.
        
        Args:
            prompt: OCR instruction prompt
            image: PIL Image object
            
        Returns:
            Extracted text from image
        """
        return self.generate_content(prompt, image)
