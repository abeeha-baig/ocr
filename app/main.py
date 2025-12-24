from services.preprocessing import process_pdf_sequential
from services.signin import process_signin_images
from services.dinein import process_dinein_images
from concurrent.futures import ThreadPoolExecutor

if __name__ == "__main__":
    pdf_file = r"C:\Users\abeeha.baig\OneDrive - Qordata\Desktop\ocr\app\input\09D263EB67D64F1B9837_HCP Spend_gWin$pt8pqpTVdMv0K3xpz4B2SPUXGGWIAlg_7188 - ST-US - GSK - ViiV - Sales_2025-10-27T163142.167_20251028061206.pdf"

    pdf_name, signin_imgs, dinein_imgs = process_pdf_sequential(
        pdf_file,
        output_dir="app/processed_pages"
    )

    with ThreadPoolExecutor() as executor:
        futures = []

        if signin_imgs:
            futures.append(
                executor.submit(process_signin_images, signin_imgs, pdf_name)
            )

        if dinein_imgs:
            futures.append(
                executor.submit(process_dinein_images, dinein_imgs, pdf_name)
            )

        for f in futures:
            f.result()
