import os
import anvil.server
from flask import Flask, request, jsonify, send_from_directory
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, BooleanObject, TextStringObject, IndirectObject
from dotenv import load_dotenv
# === CONFIGURATION ===
load_dotenv()
ANVIL_UPLINK_KEY = os.getenv("ANVIL_UPLINK_KEY")

PDF_TEMPLATE_PATH = "PQFT_Fillable_1Feb17_H.pdf"  # Replace with your actual form
OUTPUT_FOLDER = os.path.abspath("output")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
PDF_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, "filled_contract.pdf")

# === CONNECT TO ANVIL ===
anvil.server.connect(ANVIL_UPLINK_KEY)

# === INITIALIZE FLASK ===
app = Flask(__name__)

# === FIELD EXTRACTION FUNCTION ===
def extract_fields_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    fields = reader.get_fields()
    if not fields:
        return []

    output = []
    for name, field in fields.items():
        field_type = "text"
        ft = field.get("/FT")
        if ft == "/Btn":
            if "/Opt" in field:
                field_type = "radio"
            else:
                field_type = "boolean"
        elif ft == "/Tx":
            field_type = "text"

        output.append({
            "pdf_field": name,
            "question": f"What should be entered for '{name}'?",
            "type": field_type
        })
    return output

# === PDF FILL FUNCTION ===
'''
def fill_pdf(template_path, field_data, output_path):
    reader = PdfReader(template_path)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.update_page_form_field_values(writer.pages[0], field_data)

    if "/AcroForm" in reader.trailer["/Root"]:
        writer._root_object.update({
            NameObject("/AcroForm"): reader.trailer["/Root"]["/AcroForm"]
        })

    with open(output_path, "wb") as f:
        writer.write(f)
'''
# === PDF FILL FUNCTION ===
def fill_pdf(template_path, field_data, output_path):
    reader = PdfReader(template_path)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    for page in writer.pages:
        annots = page.get("/Annots")
        if not annots:
            continue

        if isinstance(annots, IndirectObject):
            annots = annots.get_object()

        if isinstance(annots, list):
            annotation_objs = [annot.get_object() for annot in annots]
        else:
            annotation_objs = [annots.get_object()]

        for obj in annotation_objs:
            field_name = obj.get("/T")
            if not field_name:
                continue
            field_name = field_name.strip()

            if field_name in field_data:
                value = field_data[field_name]

                if isinstance(value, bool):
                    on_value = "Yes"  # Fallback default

                    # Look for the checkbox's actual export value
                    ap_dict = obj.get("/AP")
                    if isinstance(ap_dict, IndirectObject):
                        ap_dict = ap_dict.get_object()

                    if ap_dict and "/N" in ap_dict:
                        appearances = ap_dict["/N"]
                        if isinstance(appearances, IndirectObject):
                            appearances = appearances.get_object()
                        if isinstance(appearances, dict):
                            for k in appearances.keys():
                                k_str = str(k)
                                print(f"Field: {field_name}")
                                print(f"Checkbox AP /N keys: {[str(k) for k in appearances.keys()]}")

                                if k_str != "/Off":
                                    on_value = k_str.strip("/")
                    export = f"/{on_value}" if value else "/Off"
                    obj.update({
                        NameObject("/V"): NameObject(export),
                        NameObject("/AS"): NameObject(export)
                    })
                else:
                    obj.update({
                        NameObject("/V"): TextStringObject(str(value))
                    })

    # Preserve AcroForm metadata
    if "/AcroForm" in reader.trailer["/Root"]:
        writer._root_object.update({
            NameObject("/AcroForm"): reader.trailer["/Root"]["/AcroForm"]
        })

    with open(output_path, "wb") as f:
        writer.write(f)


# === ROUTES ===

@app.route("/get_fields", methods=["GET"])
def get_fields():
    try:
        fields = extract_fields_from_pdf(PDF_TEMPLATE_PATH)
        return jsonify(fields)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/submit_answers", methods=["POST"])
def submit_answers():
    try:
        data = request.get_json()
        if not data or "answers" not in data:
            return jsonify({"status": "error", "message": "Missing 'answers' in request"}), 400

        field_data = data["answers"]  # ✅ Extract correct field data
        fill_pdf(PDF_TEMPLATE_PATH, field_data, PDF_OUTPUT_PATH)

        return jsonify({
            "status": "success",
            "message": "PDF filled and saved",
            "output_file": os.path.basename(PDF_OUTPUT_PATH),
            "download_url": f"/download/{os.path.basename(PDF_OUTPUT_PATH)}"
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"PDF generation failed: {str(e)}"}), 500


@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    try:
        return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# === RUN ===
if __name__ == "__main__":
    app.run(port=3030)
