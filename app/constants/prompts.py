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

prompt_ocr = """
You are an OCR model. Extract all handwritten and typed text from this image.
Output in clean Markdown with correct line breaks.\n
Convert tables into a column-based text layout. Maintain distinct vertical boundaries for each column using consistent spacing or delimiters.
If a cell is empty or merged, represent that space explicitly to ensure the column structure remains aligned and readable.\n
add or remove blank spaces from the table to fix alignments, ensuring each column lines up vertically throughout the table.\n
re-read you output of the table and fix misalignments in the layout, MAKE SURE the table layout is proper and easily readable and understandable.\n
If one text is going to the next line, don't get confused by it, just continue the text normally, within the specific column.
Do not summarize. Do not skip anything.
"""
