prompt = """
    You are an expert document analyst AI.
    
    Return a JSON object with these two keys:
    1. 'angle': The angle in degrees the image should be rotated clockwise to make the paper in the image upright.
    look at the text of this document, and identify its orientation with respect to the overall text.
    Respond with a single number: the angle in degrees the image should be rotated clockwise, make sure you don't have the image upside down or at any angle at the output to make the document upright.
    2. 'is_signin': Boolean (true/false). Set to true if you see handwriting, signatures, 
       or a signature log/table. Set to false if it is a printed invoice or receipt without signatures.
    
    Return ONLY the JSON object.
    """

# prompt_ocr = """
# You are an OCR model. Extract all handwritten and typed text from this image.
# Output in clean Markdown with correct line breaks.\n
# If a row is cut out using a pen, skip that row entirely.\n
# Convert tables into a column-based text layout. Maintain distinct vertical boundaries for each column using consistent spacing or delimiters.
# If a cell is empty or merged, represent that space explicitly to ensure the column structure remains aligned and readable.\n
# add or remove blank spaces from the table to fix alignments, ensuring each column lines up vertically throughout the table.\n
# If one text is going to the next line, don't get confused by it, just continue the text normally, within the specific column.
# if multiple tables are present, make sure each tables is properly aligned and readable.\n
# re-read your output of each table and fix misalignments in the layout, MAKE SURE each table's layout is proper and easily readable and understandable.\n
# each cell of each table should be right below its header, and each column should be properly aligned vertically.\n
# Do not summarize. Do not skip anything.
# """

prompt_ocr = """
ROLE:
You are an expert in document OCR and layout preservation.

TASK:
Analyze the image and extract ALL text exactly as it appears, preserving layout and structure.

INSTRUCTIONS:
- The image may contain tables with typed and handwritten text. Extract EVERYTHING.
- Detect the header row of each table FIRST.
- The number of columns is STRICTLY defined by the detected headers.
- Once headers are detected:
  • Fix the column order permanently
  • Every row MUST follow the same column order
- Use ONE consistent delimiter for tables: vertical pipe `|`.

TABLE ALIGNMENT RULES (CRITICAL):
- Output ALL tables using Markdown pipe-table format.
- Each column must align vertically under its header.
- If a cell is empty, still include the column using an empty placeholder.
- If text wraps to the next line in the image, merge it into the SAME cell.
- DO NOT create or remove columns under any circumstance.
- add extra spaces to maintain alignment of each column.
- DO NOT shift data between columns.
- Re-read each table after extraction and FIX misalignments so that:
  • Each row has EXACTLY the same number of columns as the header
  • All cells are correctly positioned under their respective headers

ROW HANDLING:
- If a row is crossed out or cut using a pen, SKIP that row entirely.
- Do NOT summarize.
- Do NOT omit any visible text.

OUTPUT FORMAT:
- Return output in CLEAN Markdown.
- Use proper Markdown tables with headers, separators, and rows.
- Preserve line breaks outside tables.
"""
