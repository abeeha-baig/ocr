import os
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption

def process_dinein_images(img_paths, pdf_name, output_dir="app/output"):
    os.makedirs(output_dir, exist_ok=True)
    combined_md = ""

    for source in img_paths:
        model_dir = "models/rapidocr"
        ocr_options = RapidOcrOptions(
            det_model_path=os.path.join(model_dir, "PP-OCRv4/en_PP-OCRv3_det_infer.onnx"),
            rec_model_path=os.path.join(model_dir, "PP-OCRv4/ch_PP-OCRv4_rec_server_infer.onnx"),
            cls_model_path=os.path.join(model_dir, "PP-OCRv3/ch_ppocr_mobile_v2.0_cls_train.onnx"),
        )

        pipeline_options = PdfPipelineOptions(ocr_options=ocr_options)
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        conversion_result = converter.convert(source=source)
        doc = conversion_result.document
        combined_md += doc.export_to_markdown()

    output_path = os.path.join(output_dir, f"{pdf_name}_dinein.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(combined_md)

    print(f"✅ Dinein Markdown written to: {output_path}")
