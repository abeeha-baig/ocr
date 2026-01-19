"""Prompts for OCR and AI models."""

OCR_SIGNIN_PROMPT = """
You are an expert OCR model. Extract names and credentials from the signin sheet image.
The sheet has a table with columns: PRINT NAME, SIGNATURE, and CREDENTIALS.

CRITICAL: Read each row as a COMPLETE UNIT - read the name and its corresponding credential in the SAME LINE.
ALSO, some writing would be striked out, and something would be written ahead or beside it. don't read the striked out text, read what is written beside or ahead of it.

Instructions:
- Go row by row from top to bottom
- For EACH row, read the name from the "PRINT NAME" column AND the credential from the "CREDENTIALS" column in that SAME row
- Use {HCPs} as reference for expected names
- When a name matches {HCPs}, use the exact spelling from {HCPs}, but make it upper case.
- Extract credentials EXACTLY as written in the image, character by character
- Pay close attention to periods, spaces, and capitalization in credentials
- Sometimes there is faded ink and 'A' looks like 'H', so use your best judgement
- Common credentials include: MD, CMA, NP, RN, etc.
- Check if there is a name written after "Field Employee:" in the header and extract it with credential as "Rep"
- Read the header of the page. If any of the following words appear, note the company_id:
  * GSK → company_id: 1
  * AstraZeneca → company_id: 2
  * Lilly → company_id: 3

Provide the extracted data in markdown format (one line per person):
- John Doe, MD
- Jane Smith, NP
- Robert Johnson, PA

At the end, on a new line, provide: COMPANY_ID: <number>
If no company is found, use: COMPANY_ID: 1 (default)
"""
