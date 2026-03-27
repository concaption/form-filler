import fitz  # PyMuPDF
from PyPDF2 import PdfReader
import os
import re
from pathlib import Path

SRC_DIR = Path(__file__).parent / "src"
PDFS_DIR = SRC_DIR / "pdfs"

# Crop padding around each field (in points)
CROP_PADDING = 70
# Minimum crop dimensions
MIN_CROP_WIDTH = 250
MIN_CROP_HEIGHT = 100
# Render resolution (DPI)
RENDER_DPI = 200


def sanitize_filename(name):
    """Convert field name to a safe filename."""
    return re.sub(r'[^\w\-.]', '_', name)


def extract_fields_from_pdf(pdf_path):
    """Extract all form fields with their page number and rectangle."""
    reader = PdfReader(str(pdf_path))
    fields = []

    for page_num, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        if not isinstance(annots, list):
            annots = annots.get_object()

        for annot_ref in annots:
            annot = annot_ref.get_object()
            name = str(annot.get("/T", ""))
            rect = annot.get("/Rect", [0, 0, 0, 0])
            try:
                x0 = float(rect[0])
                y0 = float(rect[1])
                x1 = float(rect[2])
                y1 = float(rect[3])
            except:
                continue
            if name:
                fields.append({
                    "name": name,
                    "page": page_num,
                    "rect": (x0, y0, x1, y1),
                })
    return fields


def generate_field_screenshots(pdf_path, output_dir):
    """Generate a cropped screenshot for each form field in the PDF."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fields = extract_fields_from_pdf(pdf_path)
    if not fields:
        print(f"  No fields found in {pdf_path}")
        return []

    doc = fitz.open(str(pdf_path))
    generated = []
    seen_names = {}

    for field in fields:
        name = field["name"]
        page_num = field["page"]
        x0, y0, x1, y1 = field["rect"]
        page = doc[page_num]
        page_height = page.rect.height

        # PDF coords have origin at bottom-left, fitz uses top-left
        # Convert: fitz_y = page_height - pdf_y
        fy0 = page_height - y1  # top in fitz coords
        fy1 = page_height - y0  # bottom in fitz coords

        # Calculate crop rect with padding
        cx0 = max(0, x0 - CROP_PADDING)
        cy0 = max(0, fy0 - CROP_PADDING)
        cx1 = min(page.rect.width, x1 + CROP_PADDING)
        cy1 = min(page.rect.height, fy1 + CROP_PADDING)

        # Ensure minimum dimensions
        cw = cx1 - cx0
        ch = cy1 - cy0
        if cw < MIN_CROP_WIDTH:
            expand = (MIN_CROP_WIDTH - cw) / 2
            cx0 = max(0, cx0 - expand)
            cx1 = min(page.rect.width, cx1 + expand)
        if ch < MIN_CROP_HEIGHT:
            expand = (MIN_CROP_HEIGHT - ch) / 2
            cy0 = max(0, cy0 - expand)
            cy1 = min(page.rect.height, cy1 + expand)

        clip = fitz.Rect(cx0, cy0, cx1, cy1)

        # Render at high DPI
        zoom = RENDER_DPI / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, clip=clip)

        # Handle duplicate field names
        safe_name = sanitize_filename(name)
        if safe_name in seen_names:
            seen_names[safe_name] += 1
            safe_name = f"{safe_name}_{seen_names[safe_name]}"
        else:
            seen_names[safe_name] = 0

        img_path = output_dir / f"p{page_num + 1}_{safe_name}.png"
        pix.save(str(img_path))
        generated.append({
            "name": name,
            "file": str(img_path),
            "page": page_num + 1,
        })

    doc.close()
    print(f"  Generated {len(generated)} field screenshots in {output_dir}")
    return generated


def generate_field_map(pdf_path, output_path):
    """Generate annotated PDF with field names overlaid (legacy full-page view)."""
    from reportlab.pdfgen import canvas
    from io import BytesIO

    reader = PdfReader(str(pdf_path))
    from PyPDF2 import PdfWriter
    writer = PdfWriter()

    for page_num, page in enumerate(reader.pages):
        media_box = page.mediabox
        page_width = float(media_box.width)
        page_height = float(media_box.height)

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
            rect = annot.get("/Rect", [0, 0, 0, 0])
            try:
                x = float(rect[0])
                y = float(rect[1])
            except:
                continue
            if name:
                fields.append((name, x, y))

        if fields:
            packet = BytesIO()
            c = canvas.Canvas(packet, pagesize=(page_width, page_height))
            c.setFont("Helvetica", 5)
            c.setFillColorRGB(1, 0, 0)
            for name, x, y in fields:
                if name:
                    c.drawString(x, y + 2, name)
                    c.setFillColorRGB(1, 0, 0, 0.3)
                    c.circle(x, y, 2, fill=1)
                    c.setFillColorRGB(1, 0, 0)
            c.save()
            packet.seek(0)
            overlay_reader = PdfReader(packet)
            page.merge_page(overlay_reader.pages[0])

        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"  Created: {output_path}")


if __name__ == "__main__":
    FIELDMAPS_DIR = SRC_DIR / "fieldmaps_pdfs"
    FIELDMAPS_DIR.mkdir(exist_ok=True)
    print("Generating field map screenshots...")
    for pdf_file in sorted(PDFS_DIR.glob("*.pdf")):
        if pdf_file.name.startswith("fieldmap_"):
            continue
        # Create a subdirectory per PDF for screenshots
        pdf_output_dir = FIELDMAPS_DIR / pdf_file.stem
        print(f"\nProcessing: {pdf_file.name}")
        try:
            generate_field_screenshots(pdf_file, pdf_output_dir)
        except Exception as e:
            print(f"  ERROR: {e}")
    print("\nDone!")
