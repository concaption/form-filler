from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import os
from pathlib import Path

SRC_DIR = Path(__file__).parent / "src"
PDFS_DIR = SRC_DIR / "pdfs"

def create_overlay(page_width, page_height, fields):
    """Create a transparent overlay PDF with field names."""
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    c.setFont("Helvetica", 5)
    c.setFillColorRGB(1, 0, 0)  # Red text
    for name, x, y in fields:
        if name:
            c.drawString(x, y + 2, name)
            # Draw a small dot at field position
            c.setFillColorRGB(1, 0, 0, 0.3)
            c.circle(x, y, 2, fill=1)
            c.setFillColorRGB(1, 0, 0)
    c.save()
    packet.seek(0)
    return packet

def generate_field_map(pdf_path, output_path):
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()

    for page_num, page in enumerate(reader.pages):
        # Get page dimensions
        media_box = page.mediabox
        page_width = float(media_box.width)
        page_height = float(media_box.height)

        # Extract field positions from annotations
        annots = page.get("/Annots")
        if not annots:
            writer.add_page(page)
            continue

        if not isinstance(annots, list):
            annots = annots.get_object()

        fields = []
        for annot_ref in annots:
            annot = annot_ref.get_object()
            name = str(annot.get("/T", ""))
            rect = annot.get("/Rect", [0,0,0,0])
            try:
                x = float(rect[0])
                y = float(rect[1])
            except:
                continue
            if name:
                fields.append((name, x, y))

        if fields:
            overlay_packet = create_overlay(page_width, page_height, fields)
            overlay_reader = PdfReader(overlay_packet)
            overlay_page = overlay_reader.pages[0]
            page.merge_page(overlay_page)

        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"  Created: {output_path}")

if __name__ == "__main__":
    FIELDMAPS_DIR = SRC_DIR / "fieldmaps_pdfs"
    FIELDMAPS_DIR.mkdir(exist_ok=True)
    print("Generating field map PDFs...")
    for pdf_file in sorted(PDFS_DIR.glob("*.pdf")):
        if pdf_file.name.startswith("fieldmap_"):
            continue
        output = FIELDMAPS_DIR / f"fieldmap_{pdf_file.name}"
        print(f"\nProcessing: {pdf_file.name}")
        try:
            generate_field_map(pdf_file, output)
        except Exception as e:
            print(f"  ERROR: {e}")
    print("\nDone!")
