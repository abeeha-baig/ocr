import os
from services.preprocessing import process_pdf_sequential
from services.signin import process_signin_images
from services.dinein import process_dinein_images
from concurrent.futures import ThreadPoolExecutor

if __name__ == "__main__":
    pdf_file = "C:\\Users\\abeeha.baig\\OneDrive - Qordata\\Desktop\\ocr\\app\\input\\09D263EB67D64F1B9837_HCP Spend_gWin$pt8pqpTVdMv0K3xpz4B2SPUXGGWIAlg_7188 - ST-US - GSK - ViiV - Sales_2025-10-27T163142.167_20251028061206.pdf"
    signin_imgs, dinein_imgs = process_pdf_sequential(pdf_file, output_dir="processed_pages")

    with ThreadPoolExecutor() as executor:
        future_signin = executor.submit(process_signin_images, signin_imgs)
        future_dinein = executor.submit(process_dinein_images, dinein_imgs)
        future_signin.result()
        future_dinein.result()
