import os
import cv2 as cv
import numpy as np
import fitz
import re
import json
import google.generativeai as genai
from PIL import Image
from constants.prompts import prompt

# We keep your specific functions as they are
def denoise_image(image): return cv.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)
def sharpen_image(image):
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv.filter2D(image, -1, kernel)
def resize_image(image, target_width=2500):
    height, width = image.shape[:2]
    scale_factor = target_width / width
    return cv.resize(image, (target_width, int(height * scale_factor)), interpolation=cv.INTER_CUBIC)
def rotate_image_logic(img, angle):
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv.getRotationMatrix2D(center, -angle, 1.0)
    return cv.warpAffine(img, M, (w, h), flags=cv.INTER_CUBIC, borderMode=cv.BORDER_REPLICATE)

def analyze_page_with_gemini(image_array):
    rgb_image = cv.cvtColor(image_array, cv.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb_image)
    model = genai.GenerativeModel("gemini-1.5-flash") # Use stable model
    try:
        response = model.generate_content([prompt, pil_img])
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        data = json.loads(match.group())
        return float(data.get("angle", 0)), data.get("is_signin", False)
    except: return 0, False

def run_preprocessing(pdf_path, output_dir):
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    doc = fitz.open(pdf_path)
    
    signin_images = []
    dinein_images = []

    for idx, page in enumerate(doc):
        temp_path = os.path.join(output_dir, f"temp_{idx}.png")
        page.get_pixmap(dpi=300).save(temp_path)
        image = cv.imread(temp_path)
        
        # Applying your logic
        image = denoise_image(image)
        image = sharpen_image(image)
        image = resize_image(image)
        angle, is_signin = analyze_page_with_gemini(image)
        
        if angle != 0: image = rotate_image_logic(image, angle)

        label = "signin" if is_signin else "dinein"
        final_path = os.path.join(output_dir, f"{pdf_name}_{label}_{idx}.png")
        cv.imwrite(final_path, image)
        os.remove(temp_path)

        if is_signin: signin_images.append(final_path)
        else: dinein_images.append(final_path)
    
    doc.close()
    return signin_images, dinein_images