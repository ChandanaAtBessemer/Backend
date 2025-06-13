from PyPDF2 import PdfReader, PdfWriter

def extract_fields(pdf_path):
    reader = PdfReader(pdf_path)
    fields = reader.get_fields()
    if not fields:
        raise ValueError("No form fields found.")
    return fields

def fill_fields(pdf_path, field_data, output_path):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.update_page_form_field_values(writer.pages[0], field_data)
    with open(output_path, "wb") as f:
        writer.write(f)
