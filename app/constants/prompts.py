"""Prompts for OCR and AI models."""

OCR_SIGNIN_PROMPT = """
You are an expert OCR model. Extract names and credentials from the signin sheet image.

CRITICAL: Read each row as a COMPLETE UNIT - read the name and its corresponding credential in the SAME LINE.
You MUST extract ALL names and credentials from the image. If a particular credential is missing, leave it blank but still extract the name.
Also, sometimes a name or a credential is striked out and a new one is written beside it or above it, use YOUR BEST JUDGEMENT HERE TO FETCH THAT NAME. You can not skip such a case. Therefore, be very careful while reading striked out text.
sometimes, the entire row's writing is really messy, but YOU HAVE TO EXTRACT IT, use YOUR BEST JUDGEMENT.
If a complete row is striked out, SKIP that row entirely.
Read the correct credential for each name, THIS IS HIGHLY CRITICAL.

Instructions:
- Go row by row from top to bottom
- For EACH row, read the name and the credential carefully from their respective columns.
- Use {HCPs} as reference for expected names.
- CREDENTIAL HINTS (from registration): {credential_hints}
  * Use only to help read unclear handwriting - always record what's ACTUALLY WRITTEN on page
- CAPITALIZATION RULES (VERY IMPORTANT):
  * Convert ALL OCR'd names to lowercase first
  * ONLY if a name matches one from {HCPs}, use the exact spelling from {HCPs} and make it UPPER CASE
  * Names that don't match {HCPs} MUST remain in lowercase
  * This is applicable to both header name and the body. try to match the header name with {HCPs} as well, if it matches, use the exact spelling from {HCPs} and make it UPPER CASE, if not, keep it in lowercase and assign credential 'rep' to it.
- Read the credentials VERY CAREFULLY. Read exactly character by character. writings are variable, so some handwiritings would be written small, some large. Create your judment row wise. 
- Extract credential as is, the spaces, the special characters, all should be fetched as is. 
- Check if there is a name written after "Field Employee:" in the header, and ONLY if that name appears in the body as well, prioritize the body occurrence of that name. if it does not appear in the body, keep the header name with credential as 'rep'.
CRITICAL: Do not get confused or skip anything in the body due to header information. The header information is just additional information, but the body of the page is the most critical part and you MUST read it carefully and extract all names and credentials from there. If a name appears both in the header and the body, prioritize the body occurrence of that name.
If not, add the header name in the last, so that it does not interfere with reading the body of the page, and assign it the credential 'rep'.
- Read the header of the page. If any of the following words appear, note the company_id:
  * GSK → company_id: 1
  * AstraZeneca → company_id: 2
  * Lilly → company_id: 3

OUTPUT FORMAT (FOLLOW EXACTLY - DO NOT DEVIATE):
You MUST output each person on a separate line in this EXACT format:
- Name, Credential
match this exact format: starts with "-" then space, then name, then comma, then space, and lastly the credential.

After all names are listed, on a NEW LINE provide:
COMPANY_ID: <number>

If no company is found, use: COMPANY_ID: 1
"""
