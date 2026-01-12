"""Prompts for OCR and AI models."""

OCR_SIGNIN_PROMPT = """
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
