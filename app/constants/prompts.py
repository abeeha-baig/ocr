"""Prompts for OCR and AI models."""

OCR_SIGNIN_PROMPT = """
You are an expert OCR model. Extract names and credentials from the signin sheet image.

Instructions:
- Go row by row from top to bottom
- For EACH row, read the name, credential, and presence of the signature carefully from their respective columns.
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
- Check if there is a name written after "Field Employee:" in the header, and ONLY if that name appears in the body as well, prioritize the body occurrence of that name, if the body occurrence does not have the credential 'rep' or 'psr', make it 'rep'. if it does not appear in the body, keep the header name with credential as 'rep'.
- Also, the one's that did not consume, write DNC in front of their names.

CRITICAL:
You MUST extract ALL names and credentials from the image.
There would be some cases when the name is present, but the credential is not, or the signature is not. In such cases, whatever is present, you have to fetch it, and what's missing should be left blank.
Also, sometimes a name or a credential is striked out and a new one is written beside it or above it, use YOUR BEST JUDGEMENT HERE TO FETCH THAT NAME. You can not skip such a case. Therefore, be very careful while reading striked out text.\n
YOU CAN NOT SKIP A ROW, if it is being difficult to read. Look closely, and whatever you understand from it, fetch it.\n
**ONLY** If a complete row is striked out, only then you can skip it.
Read the correct credential for each name, THIS IS HIGHLY CRITICAL.

CRITICAL: Do not get confused or skip anything in the body due to header information. The header information is just additional information, but the body of the page is the most critical part and you MUST read it carefully and extract all names and credentials from there.
If a name appears both in the header and the body, prioritize the body occurrence of that name.
If not, add the header name in the last, so that it does not interfere with reading the body of the page, and assign it the credential 'rep'.
- Read the header of the page. If any of the following words appear, note the company_id:
  * GSK → company_id: 1
  * AstraZeneca → company_id: 2
  * Lilly → company_id: 3

OUTPUT FORMAT (FOLLOW EXACTLY - DO NOT DEVIATE):
You MUST output each person on a separate line in this EXACT format:
- Name, Credential, [signature present] - this format when all the three pieces of information are present
- Name, Credential, [] - this format when signature is not present.
- Name, [], [signature present] - this format when credential is not present. 
and vice versa.

After all names are listed, on a NEW LINE provide:
COMPANY_ID: <number>

If no company is found, use: COMPANY_ID: 1
"""
