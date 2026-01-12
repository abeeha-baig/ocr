import pandas as pd
import re
import os
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

# CSV path
csv_path = r"C:\Users\abeeha.baig\OneDrive - Qordata\Desktop\ocr\app\services\Extract_syneos_GSK_20251028000000_20251028051654.csv"

# Signin image path
signin_image_path = r"C:\Users\abeeha.baig\OneDrive - Qordata\Desktop\ocr\app\pages\2DBC20CE104A400AAB8D_HCP Spend_gWin$pt8sY00RZ$sJrt$pWJhKhvJKbxyeHgSdg_7025 - ST-US - GSK - Vacancy Management (0325)_2025-10-27T170222.733_20251028061146.png"
# Load CSV
df = pd.read_csv(csv_path, sep="|", dtype=str)
df["ExpenseV3_ID"] = df["ExpenseV3_ID"].str.strip()

# Extract expense ID from image name
expense_id = re.search(r"HCP Spend_(gWin\$[^_]+)", signin_image_path).group(1)

# Filter matching rows
result = df.loc[
    df["ExpenseV3_ID"] == expense_id,
    ["AttendeeV3_FirstName", "AttendeeV3_LastName", "ExpenseV3_ID"]
]

print(result)
credential = ["PSR", "Rep", "OTH", "ANP", "CNM", "CNS", "CRNA", "DC", "DDS", "DMD", "DO", "DOJD", "DOMB", "DOMS", "DPM", "MD", "MDJD", "MDMB", "MDMS", "MSD", "NP", "OD", "PA", "RPA"]

# Combine first and last names
result["AttendeeV3_FullName"] = result["AttendeeV3_FirstName"] + " " + result["AttendeeV3_LastName"]

# Prepare HCPs list, removing NaNs
HCPs = [str(name).strip() for name in result["AttendeeV3_FullName"].tolist() if pd.notna(name)]
print(HCPs)

# Configure Gemini API
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-2.5-flash"

def process_signin_images(img_paths, output_image_path, output_dir="app/output"):
    combined_md = ""
    os.makedirs(output_dir, exist_ok=True)

    model = genai.GenerativeModel(MODEL_NAME)

    prompt_ocr = """
    You are an expert OCR model. Extract the names from the signin sheet image provided.
    The signin sheet contains handwritten names of attendees. Utilize {HCPs} to understand which names might be present.\n
    The signin sheet also contains the credentials of each attendee, utilize {credential} to understand which credentials might be present.\n
    There might be some names and credentials that are not present in {HCPs} and {credential}, but extract all names and their credentials from the image.\n
    When you are confident that a name matches one from {HCPs}, use the spelling and the exact name from {HCPs} for that particular name.\n
    Try to read each character of the credential very carefully, since it is handwritten and might be unclear.\n
    Provide the extracted names in markdown format:\n
    - John Doe, MD
    - Jane Smith, CMA
    """

    for img_path in img_paths:
        prompt = prompt_ocr.format(HCPs=HCPs, credential=credential)
        resp = model.generate_content([prompt, Image.open(img_path)])
        combined_md += f"### Signin sheet: {os.path.basename(img_path)}\n"
        combined_md += resp.text or "" + "\n\n"

    # output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(output_image_path))[0]}_signin.md")
    # with open(output_path, "w", encoding="utf-8") as f:
    #     f.write(combined_md)

    # print(f"✅ Signin Markdown written to: {output_path}")
    # return combined_md
    return combined_md
# Call the function
signin_md = process_signin_images([signin_image_path], signin_image_path)
print(signin_md)
