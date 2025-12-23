import os
import cv2 as cv
import re
import numpy as np
import fitz
import google.generativeai as genai
from PIL import Image
import dotenv
import json
from constants.prompts import prompt

dotenv.load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-2.5-flash-lite"

def denoise_image(image):
    return cv.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)

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
    rotated = cv.warpAffine(img, M, (w, h), flags=cv.INTER_CUBIC, borderMode=cv.BORDER_REPLICATE)
    return rotated

def analyze_page_with_gemini(image_array):
    rgb_image = cv.cvtColor(image_array, cv.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb_image)
    model = genai.GenerativeModel(MODEL_NAME)
    try:
        response = model.generate_content([prompt, pil_img])
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in response")
        data = json.loads(match.group())
        return float(data.get("angle", 0)), data.get("is_signin", False)
    except Exception as e:
        print(f"⚠️ Gemini Analysis failed: {e}")
        return 0, False

def process_pdf_sequential(pdf_path, output_dir="processed_pages"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    doc = fitz.open(pdf_path)
    temp_files = []

    for idx, page in enumerate(doc):
        temp_path = os.path.join(output_dir, f"temp_{idx+1}.png")
        page.get_pixmap(dpi=300).save(temp_path)
        temp_files.append(temp_path)
    doc.close()

    signin_images = []
    dinein_images = []

    for img_path in temp_files:
        try:
            image = cv.imread(img_path)
            image = denoise_image(image)
            image = sharpen_image(image)
            image = resize_image(image, target_width=2500)
            angle, is_signin = analyze_page_with_gemini(image)
            if angle != 0:
                image = rotate_image_logic(image, angle)
            final_name = f"{pdf_name}_{'signin' if is_signin else 'dinein'}_{os.path.basename(img_path)}"
            final_path = os.path.join(output_dir, final_name)
            cv.imwrite(final_path, image)
            if is_signin:
                signin_images.append(final_path)
            else:
                dinein_images.append(final_path)
            if os.path.exists(img_path):
                os.remove(img_path)
        except Exception as e:
            print(f"⚠️ Error processing {img_path}: {e}")

    return signin_images, dinein_images
