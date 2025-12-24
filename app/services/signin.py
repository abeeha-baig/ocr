import os
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv
from constants.prompts import prompt_ocr

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-3-flash-preview"

def process_signin_images(img_paths, pdf_name, output_dir="app/output"):
    combined_md = ""
    os.makedirs(output_dir, exist_ok=True)

    model = genai.GenerativeModel(MODEL_NAME)

    for img_path in img_paths:
        img = Image.open(img_path)
        resp = model.generate_content([prompt_ocr, img])
        combined_md += resp.text or ""

    output_path = os.path.join(output_dir, f"{pdf_name}_signin.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(combined_md)

    print(f"✅ Signin Markdown written to: {output_path}")
