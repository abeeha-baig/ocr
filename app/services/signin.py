import sys
import os
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
from constants.prompts import prompt_ocr

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

img_path = "output/09D263EB67D64F1B9837_HCP Spend_gWin$pt8pqpTVdMv0K3xpz4B2SPUXGGWIAlg_7188 - ST-US - GSK - ViiV - Sales_2025-10-27T163142.167_20251028061206_dinein_2.png"

def signin_ocr(img_path):
    img = Image.open(img_path)

    model = genai.GenerativeModel("gemini-3-flash-preview")
    # model = genai.GenerativeModel("gemini-2.5-flash")

    resp = model.generate_content([prompt_ocr, img])
    md = resp.text or ""
    output_path = os.path.join("output", f"{os.path.splitext(os.path.basename(img_path))[0]}-signin.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
        print(md)
    print(f"Markdown output written to: {output_path}")
signin_ocr(img_path)
