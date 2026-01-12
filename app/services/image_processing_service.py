"""Image processing service for preprocessing images before OCR."""

import numpy as np
import cv2
from PIL import Image, ImageEnhance


class ImageProcessingService:
    """Service for image preprocessing and enhancement."""
    
    @staticmethod
    def deskew_image(image_path, max_angle=10):
        """
        Deskew and enhance image for better OCR accuracy.
        
        Args:
            image_path: Path to the image file
            max_angle: Maximum angle for rotation correction (default: 10 degrees)
            
        Returns:
            PIL Image object (processed)
        """
        # Read image
        img = cv2.imread(image_path)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold to get binary image
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Find all contours
        coords = np.column_stack(np.where(thresh > 0))
        
        # Get rotation angle
        angle = cv2.minAreaRect(coords)[-1]
        
        # Adjust angle - only correct small skews (between -max_angle and max_angle degrees)
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Only apply rotation if angle is reasonable
        if abs(angle) < max_angle:
            # Rotate image to deskew
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            print(f"✓ Image deskewed by {angle:.2f} degrees")
        else:
            rotated = img
            print(f"✓ Skipping rotation (angle {angle:.2f}° too large), using original orientation")
        
        # Convert back to PIL Image
        rotated_pil = Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
        
        # Enhance image
        enhanced_image = ImageProcessingService.enhance_image(rotated_pil)
        
        return enhanced_image
    
    @staticmethod
    def enhance_image(pil_image, contrast=1.5, sharpness=1.5):
        """
        Enhance image contrast and sharpness.
        
        Args:
            pil_image: PIL Image object
            contrast: Contrast enhancement factor (default: 1.5)
            sharpness: Sharpness enhancement factor (default: 1.5)
            
        Returns:
            Enhanced PIL Image object
        """
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(pil_image)
        enhanced = enhancer.enhance(contrast)
        
        # Enhance sharpness
        sharpness_enhancer = ImageEnhance.Sharpness(enhanced)
        final_image = sharpness_enhancer.enhance(sharpness)
        
        return final_image
