import pandas as pd
import re
import os
import sys
import google.generativeai as genai
from PIL import Image, ImageEnhance
import numpy as np
import cv2
from dotenv import load_dotenv

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# CSV path
csv_path = r"C:\Users\abeeha.baig\OneDrive - Qordata\Desktop\ocr-2\app\tables\Extract_syneos_GSK_20251028000000_20251028051654.csv"
# Signin image path
signin_image_path = r"C:\Users\abeeha.baig\OneDrive - Qordata\Desktop\ocr-2\app\pages\2DBC20CE104A400AAB8D_HCP Spend_gWin$pt8sY00RZ$sJrt$pWJhKhvJKbxyeHgSdg_7025 - ST-US - GSK - Vacancy Management (0325)_2025-10-27T170222.733_20251028061146.png"

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

# Combine first and last names
result["AttendeeV3_FullName"] = result["AttendeeV3_FirstName"] + " " + result["AttendeeV3_LastName"]

# Prepare HCPs list, removing NaNs
HCPs = [str(name).strip() for name in result["AttendeeV3_FullName"].tolist() if pd.notna(name)]
print(HCPs)

# Load HCP credentials from local Excel file
print("\nLoading HCP credentials from Excel file...")
credential_mapping_file = os.path.join(os.getcwd(), "PossibleNames_to_Credential_Mapping.xlsx")

try:
    hcp_credentials_df = pd.read_excel(credential_mapping_file)
    
    # Filter for HCP classification and company_id=1
    hcp_credentials_df = hcp_credentials_df[
        (hcp_credentials_df['Classification'] == 'HCP') & 
        (hcp_credentials_df['company_id'] == 1)
    ]
    
    # Create credential mapping dictionary
    hcp_credential_mapping = dict(zip(
        hcp_credentials_df['PossibleNames'], 
        hcp_credentials_df['Credential']
    ))
    
    print(f"Loaded {len(hcp_credential_mapping)} HCP credential mappings for company_id=1")
except Exception as e:
    print(f"Warning: Could not load Excel file ({e}). Loading from database instead...")
    from app.services.credential_service import CredentialService
    with CredentialService() as cred_service:
        hcp_credentials_df = cred_service.get_hcp_credentials_for_company(company_id=1)
        hcp_credential_mapping = cred_service.get_hcp_credentials_dict(company_id=1)
    print(f"Loaded {len(hcp_credential_mapping)} HCP credential mappings from database")

# Configure Gemini API
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-2.5-flash"

def deskew_image(image_path):
    """Deskew and enhance image for better OCR accuracy."""
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
    
    # Adjust angle - only correct small skews (between -10 and 10 degrees)
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    
    # Only apply rotation if angle is reasonable (< 10 degrees)
    if abs(angle) < 10:
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
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(rotated_pil)
    enhanced = enhancer.enhance(1.5)
    
    # Enhance sharpness
    sharpness_enhancer = ImageEnhance.Sharpness(enhanced)
    final_image = sharpness_enhancer.enhance(1.5)
    
    return final_image

def process_signin_images(img_paths, output_image_path, output_dir="app/output"):
    combined_md = ""
    os.makedirs(output_dir, exist_ok=True)

    model = genai.GenerativeModel(MODEL_NAME)

    prompt_ocr = """
    You are an expert OCR model. Extract names and credentials from the signin sheet image.
    The sheet has a table with columns: PRINT NAME, SIGNATURE, and CREDENTIALS.
    
    IMPORTANT: Process the columns SEPARATELY:
    
    Step 1: Read ALL names from the "PRINT NAME" column (leftmost column)
    - Use {HCPs} as reference for expected names
    - When a name matches {HCPs}, use the exact spelling from {HCPs}
    - Check if there is a name written after "Field Employee:" in the header and extract it with credential as "Rep"
    
    Step 2: Read ALL credentials from the "CREDENTIALS" column (rightmost column) INDEPENDENTLY
    - Do NOT try to match credentials while reading names
    - Read each credential entry in the credentials column from top to bottom, very carefully
    - Extract credentials EXACTLY as written in the image, character by character
    - Even if a credential looks unusual or abbreviated, extract it exactly as you see it
    - Pay close attention to periods, spaces, and capitalization
    
    Step 3: Match names with credentials by their row position (1st name → 1st credential, 2nd name → 2nd credential, etc.)
    
    Provide the extracted data in markdown format:
    - John Doe, MD
    - Jane Smith, NP
    - Robert Johnson, PA
    """

    for img_path in img_paths:
        # Deskew and enhance image
        processed_image = deskew_image(img_path)
        
        prompt = prompt_ocr.format(HCPs=HCPs)
        resp = model.generate_content([prompt, processed_image])
        combined_md += f"### Signin sheet: {os.path.basename(img_path)}\n"
        combined_md += resp.text or "" + "\n\n"

    # output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(output_image_path))[0]}_signin.md")
    # with open(output_path, "w", encoding="utf-8") as f:
    #     f.write(combined_md)

    # print(f"✅ Signin Markdown written to: {output_path}")
    # return combined_md
    return combined_md

def classify_credentials(ocr_results, mapping_file="PossibleNames_to_Credential_Mapping.xlsx"):
    """
    Parse OCR results and classify credentials using rule-based exact matching.
    Classification is purely based on lookup in the mapping file - no AI involved.
    """
    # Load mapping file with all credential mappings
    mapping_df = pd.read_excel(mapping_file)
    
    # Normalize mapping data for case-insensitive matching
    mapping_df['PossibleNames_Upper'] = mapping_df['PossibleNames'].str.upper().str.strip()
    mapping_df['Credential_Upper'] = mapping_df['Credential'].str.upper().str.strip()
    
    # Parse markdown OCR results
    lines = ocr_results.split('\n')
    extracted_data = []
    
    for line in lines:
        # Match markdown format: "- Name, Credential"
        match = re.match(r'-\s*(.+?),\s*(.+)$', line.strip())
        if match:
            name = match.group(1).strip()
            credential_ocr = match.group(2).strip()
            extracted_data.append({
                'Name': name,
                'Credential_OCR': credential_ocr
            })
    
    if not extracted_data:
        print("⚠️ No data extracted from OCR results")
        return pd.DataFrame()
    
    # Create DataFrame
    results_df = pd.DataFrame(extracted_data)
    
    # Rule-based classification: exact lookup in mapping file
    classifications = []
    matched_credentials = []
    
    for idx, row in results_df.iterrows():
        credential_ocr = row['Credential_OCR'].upper().strip()
        
        # Rule 1: Try exact match in PossibleNames column
        match = mapping_df[mapping_df['PossibleNames_Upper'] == credential_ocr]
        
        # Rule 2: If not found, try exact match in Credential column
        if match.empty:
            match = mapping_df[mapping_df['Credential_Upper'] == credential_ocr]
        
        # Apply classification based on match
        if not match.empty:
            # Use first match (exact lookup from mapping file)
            classifications.append(match.iloc[0]['Classification'])
            matched_credentials.append(match.iloc[0]['Credential'])
        else:
            # No match found in mapping file
            classifications.append('Unknown')
            matched_credentials.append(row['Credential_OCR'])
    
    results_df['Credential_Standardized'] = matched_credentials
    results_df['Classification'] = classifications
    
    # Save to Excel
    output_file = "OCR_Results_Classified.xlsx"
    results_df.to_excel(output_file, index=False)
    print(f"\n✅ Classified results saved to: {output_file}")
    print(f"\nSummary:")
    print(f"  Total entries: {len(results_df)}")
    print(f"  HCP: {sum(results_df['Classification'] == 'HCP')}")
    print(f"  Field Employee: {sum(results_df['Classification'] == 'Field Employee')}")
    print(f"  Unknown: {sum(results_df['Classification'] == 'Unknown')}")
    
    return results_df

# Call the function
signin_md = process_signin_images([signin_image_path], signin_image_path)
print(signin_md)

# Classify credentials
classified_results = classify_credentials(signin_md)
print("\nClassified Results:")
print(classified_results)
