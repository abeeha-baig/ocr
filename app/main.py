from services.preprocessing import process_pdf_sequential
from services.signin import process_signin_images
from services.dinein import process_dinein_images
from concurrent.futures import ThreadPoolExecutor

if __name__ == "__main__":
    pdf_file = r"C:/Users/abeeha.baig/OneDrive - Qordata/Desktop/ocr/app/input/06288089CD0841F9A264_HCP Spend_gWin$pt8of30IvCD9Z8vilFhU$ptv2n92Rl7Q_7188 - ST-US - GSK - ViiV - Sales_2025-10-27T213241.7_20251028061209.pdf"

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
