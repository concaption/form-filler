"""PDF form filler engine. Maps CRM contact data to PDF form fields."""

import json
import os
import copy
from pathlib import Path
from typing import Optional
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, ArrayObject, TextStringObject, BooleanObject

MAPPINGS_DIR = Path(__file__).parent / "field_mappings"
PDFS_DIR = Path(__file__).parent / "pdfs"
OUTPUT_DIR = Path(__file__).parent / "output"


def get_available_forms() -> list:
    """Return list of available form mappings."""
    forms = []
    for f in sorted(MAPPINGS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        with open(f) as fh:
            data = json.load(fh)
        forms.append({
            "mapping_file": f.name,
            "form_name": data.get("form_name", f.stem),
            "provider": data.get("provider", ""),
            "product": data.get("product", ""),
            "pdf_file": data.get("pdf_file", ""),
        })
    return forms


def _transform_date_field(date_str: str, part: str) -> str:
    """Extract day/month/year from a date string like '1979-02-02'."""
    if not date_str:
        return ""
    parts = date_str.split("-")
    if len(parts) != 3:
        return date_str
    year, month, day = parts
    if part == "day":
        return day
    elif part == "month":
        return month
    elif part == "year":
        return year
    return date_str


def _resolve_value(field_config: dict, contact: dict) -> Optional[str]:
    """Resolve a field mapping to a value from the contact data.

    Returns the value to set, or None if the field shouldn't be filled.
    """
    crm_field = field_config.get("crm_field")
    if crm_field is None:
        return None

    raw_value = contact.get(crm_field, "")
    if raw_value is None:
        raw_value = ""

    transform = field_config.get("transform")
    if transform in ("day", "month", "year"):
        return _transform_date_field(str(raw_value), transform)

    return str(raw_value)


def _should_check(field_config: dict, contact: dict) -> Optional[bool]:
    """For checkboxes, determine if they should be checked.

    Returns True to check, False to uncheck, None to skip.
    """
    crm_field = field_config.get("crm_field")
    match_value = field_config.get("match_value")

    if crm_field is None:
        return None

    contact_value = str(contact.get(crm_field, "")).strip().lower()
    if match_value is not None:
        return contact_value == match_value.strip().lower()

    # Boolean field
    return bool(contact.get(crm_field))


def fill_form(mapping_file: str, contact: dict, extra_fields: dict = None) -> str:
    """Fill a PDF form with contact data.

    Args:
        mapping_file: Name of the mapping JSON file (e.g., 'aviva_prsa.json')
        contact: Contact data dict from CRM
        extra_fields: Additional field values not in CRM (e.g., contribution amount)

    Returns:
        Path to the output PDF file.
    """
    # Load mapping
    mapping_path = MAPPINGS_DIR / mapping_file
    with open(mapping_path) as f:
        mapping = json.load(f)

    field_map = mapping.get("field_map", {})
    pdf_file = mapping.get("pdf_file", "")
    pdf_path = PDFS_DIR / pdf_file

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Merge contact with extra fields
    merged = dict(contact)
    if extra_fields:
        merged.update(extra_fields)

    # Read the PDF
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)

    # Set NeedAppearances so PDF viewers regenerate field visuals
    try:
        if "/AcroForm" not in writer._root_object:
            acroform = reader.trailer["/Root"].get_object().get("/AcroForm")
            if acroform:
                writer._root_object[NameObject("/AcroForm")] = acroform.get_object()
        if "/AcroForm" in writer._root_object:
            writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
    except Exception:
        pass

    # Build the update dicts
    text_updates = {}
    checkbox_updates = {}

    for pdf_field_name, config in field_map.items():
        if pdf_field_name.startswith("__"):
            continue  # Skip comments

        if isinstance(config, str):
            # Simple direct mapping: "Text Field 255": "first_name"
            value = merged.get(config, "")
            if value:
                text_updates[pdf_field_name] = str(value)
            continue

        if "match_value" in config:
            # Checkbox with match value
            should_check = _should_check(config, merged)
            if should_check is not None:
                checkbox_updates[pdf_field_name] = should_check
        else:
            # Text field
            value = _resolve_value(config, merged)
            if value:
                text_updates[pdf_field_name] = value

    # Apply all updates by directly modifying annotations on each page
    for page in writer.pages:
        annots = page.get("/Annots")
        if not annots:
            continue
        if isinstance(annots, ArrayObject):
            annot_list = annots
        else:
            annot_list = annots.get_object()

        for annot_ref in annot_list:
            annot = annot_ref.get_object()
            field_name = str(annot.get("/T", ""))

            if field_name in text_updates:
                annot[NameObject("/V")] = TextStringObject(text_updates[field_name])

            elif field_name in checkbox_updates:
                if checkbox_updates[field_name]:
                    annot[NameObject("/V")] = NameObject("/Yes")
                    annot[NameObject("/AS")] = NameObject("/Yes")
                else:
                    annot[NameObject("/V")] = NameObject("/Off")
                    annot[NameObject("/AS")] = NameObject("/Off")

    # Save output
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = contact.get("full_name", "unknown").replace(" ", "_")
    form_label = mapping.get("form_name", mapping_file).replace(" ", "_").replace("/", "-")
    output_filename = f"{safe_name}_{form_label}.pdf"
    output_path = OUTPUT_DIR / output_filename

    with open(output_path, "wb") as f:
        writer.write(f)

    return str(output_path)


if __name__ == "__main__":
    # Quick test
    from crm_client import search_contacts

    contacts = search_contacts("Murphy")
    if contacts:
        contact = contacts[0]
        print(f"Filling form for: {contact['full_name']}")
        output = fill_form("aviva_prsa.json", contact)
        print(f"Output: {output}")
    else:
        print("No contacts found")
