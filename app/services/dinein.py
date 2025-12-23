import os

from huggingface_hub import snapshot_download

from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import (
    ConversionResult,
    DocumentConverter,
    InputFormat,
    PdfFormatOption,
)

def dinein_ocr():
    # Source document to convert
    source = "output/0194ACA72EC64CC4B345_HCP Spend_gWin$pt8pq1EJb$s7LHi9$pXfl2vAFUEnruYfQ_7025 - ST-US - GSK - Vacancy Management (0325)_2025-10-27T131424.877_20251028061210_dinein_2.png"

    #the models are already in the models folder
    model_dir = "models/rapidocr"
    det_model_path = os.path.join(model_dir, "PP-OCRv4", "en_PP-OCRv3_det_infer.onnx")
    rec_model_path = os.path.join(model_dir, "PP-OCRv4", "ch_PP-OCRv4_rec_server_infer.onnx")
    cls_model_path = os.path.join(model_dir, "PP-OCRv3", "ch_ppocr_mobile_v2.0_cls_train.onnx")
    ocr_options = RapidOcrOptions(
        det_model_path=det_model_path,
        rec_model_path=rec_model_path,
        cls_model_path=cls_model_path,
    )

    pipeline_options = PdfPipelineOptions(
        ocr_options=ocr_options,
    )

    # Convert the document
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            ),
        },
    )

    conversion_result: ConversionResult = converter.convert(source=source)
    doc = conversion_result.document
    md = doc.export_to_markdown()

    # Create the output filename based on the input filename
    input_filename = os.path.basename(source)
    input_filename_without_extension = os.path.splitext(input_filename)[0]
    output_filename = f"{input_filename_without_extension}.md"

    # Create the 'output' directory if it doesn't exist
    output_directory = "output"
    os.makedirs(output_directory, exist_ok=True)

    output_path = os.path.join(output_directory, output_filename)

    # Write the Markdown output to the file
    with open(output_path, 'w', encoding='utf-8') as outfile:
        outfile.write(md)

    print(f"Markdown output written to: {output_path}")

if __name__ == "__main__":
    dinein_ocr()