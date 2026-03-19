"""PDF form filler engine. Maps CRM contact data to PDF form fields."""

import json
import os
import copy
import logging
from pathlib import Path
from typing import Optional
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, ArrayObject, TextStringObject, BooleanObject

from config import MAPPINGS_DIR, PDFS_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)


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
    # Static value — always fills this exact string
    static = field_config.get("static_value")
    if static is not None:
        return str(static)

    crm_field = field_config.get("crm_field")
    if crm_field is None:
        return None

    raw_value = contact.get(crm_field, "")
    if raw_value is None:
        raw_value = ""

    transform = field_config.get("transform")
    if transform in ("day", "month", "year"):
        return _transform_date_field(str(raw_value), transform)
    if transform == "email_prefix":
        return str(raw_value).split("@")[0] if "@" in str(raw_value) else str(raw_value)
    if transform == "email_domain":
        return str(raw_value).split("@")[1] if "@" in str(raw_value) else ""
    if transform == "date_ddmmyyyy":
        parts = str(raw_value).split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return str(raw_value)
    if transform == "date_ddmmyyyy_noslash":
        parts = str(raw_value).split("-")
        if len(parts) == 3:
            return f"{parts[2]}{parts[1]}{parts[0]}"
        return str(raw_value)
    if transform == "strip_spaces":
        return str(raw_value).replace(" ", "")

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
    logger.info("Loading mapping: %s", mapping_path)
    with open(mapping_path) as f:
        mapping = json.load(f)

    field_map = mapping.get("field_map", {})
    pdf_file = mapping.get("pdf_file", "")
    pdf_path = PDFS_DIR / pdf_file

    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info("Source PDF: %s (%d bytes)", pdf_path, pdf_path.stat().st_size)

    # Merge contact with extra fields
    merged = dict(contact)
    if extra_fields:
        merged.update(extra_fields)

    logger.info("Contact: %s (id=%s)", merged.get("full_name", "?"), merged.get("id", "?"))
    logger.debug("Contact data: %s", {k: v for k, v in merged.items() if v})

    # Read the PDF
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    logger.info("PDF loaded: %d pages", len(reader.pages))

    # List all form fields in the PDF for debugging
    pdf_field_names = set()
    for page_idx, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        annot_list = annots if isinstance(annots, ArrayObject) else annots.get_object()
        for annot_ref in annot_list:
            annot = annot_ref.get_object()
            fname = str(annot.get("/T", ""))
            ftype = str(annot.get("/FT", ""))
            if fname:
                pdf_field_names.add(fname)
                logger.debug("  PDF field [page %d]: %r  type=%s", page_idx + 1, fname, ftype)
    logger.info("PDF contains %d form fields", len(pdf_field_names))

    # Set NeedAppearances so PDF viewers regenerate field visuals
    try:
        if "/AcroForm" not in writer._root_object:
            acroform = reader.trailer["/Root"].get_object().get("/AcroForm")
            if acroform:
                writer._root_object[NameObject("/AcroForm")] = acroform.get_object()
                logger.debug("Copied AcroForm from reader to writer")
        if "/AcroForm" in writer._root_object:
            writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
            logger.debug("Set NeedAppearances = True")
        else:
            logger.warning("No AcroForm found in PDF — form fields may not be fillable")
    except Exception as e:
        logger.warning("Failed to set NeedAppearances: %s", e)

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
                logger.info("  MAP  %r -> %r = %r", pdf_field_name, config, str(value))
            else:
                logger.debug("  SKIP %r -> %r (empty value)", pdf_field_name, config)
            continue

        if "match_value" in config:
            # Checkbox with match value
            should_check = _should_check(config, merged)
            if should_check is not None:
                checkbox_updates[pdf_field_name] = should_check
                logger.info("  CHECK %r -> crm=%r match=%r => %s",
                            pdf_field_name, config.get("crm_field"),
                            config.get("match_value"), should_check)
        else:
            # Text field
            value = _resolve_value(config, merged)
            if value:
                text_updates[pdf_field_name] = value
                logger.info("  MAP  %r [%s] -> %r = %r",
                            pdf_field_name, config.get("label", ""),
                            config.get("crm_field"), value)
            else:
                logger.debug("  SKIP %r [%s] -> %r (empty/null)",
                             pdf_field_name, config.get("label", ""),
                             config.get("crm_field"))

    # Check for mapped fields that don't exist in the PDF
    missing_in_pdf = set(text_updates.keys()) | set(checkbox_updates.keys())
    missing_in_pdf -= pdf_field_names
    if missing_in_pdf:
        logger.warning("Mapped fields NOT FOUND in PDF: %s", sorted(missing_in_pdf))

    logger.info("Updates prepared: %d text fields, %d checkboxes", len(text_updates), len(checkbox_updates))

    # Apply all updates by directly modifying annotations on each page
    fields_written = 0
    for page_idx, page in enumerate(writer.pages):
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
                # Remove stale appearance stream so viewer must regenerate it
                if NameObject("/AP") in annot:
                    del annot[NameObject("/AP")]
                fields_written += 1
                logger.debug("  WROTE text [page %d] %r = %r", page_idx + 1, field_name, text_updates[field_name])

            elif field_name in checkbox_updates:
                if checkbox_updates[field_name]:
                    annot[NameObject("/V")] = NameObject("/Yes")
                    annot[NameObject("/AS")] = NameObject("/Yes")
                else:
                    annot[NameObject("/V")] = NameObject("/Off")
                    annot[NameObject("/AS")] = NameObject("/Off")
                fields_written += 1
                logger.debug("  WROTE checkbox [page %d] %r = %s", page_idx + 1, field_name, checkbox_updates[field_name])

    # Handle radio button groups (parent field with /Kids)
    radio_updates = {k: v for k, v in field_map.items()
                     if not k.startswith("__") and isinstance(v, dict)
                     and v.get("radio_group")}
    if radio_updates:
        for page_idx, page in enumerate(writer.pages):
            annots = page.get("/Annots")
            if not annots:
                continue
            annot_list = annots if isinstance(annots, ArrayObject) else annots.get_object()
            for annot_ref in annot_list:
                annot = annot_ref.get_object()
                parent_ref = annot.get("/Parent")
                if not parent_ref:
                    continue
                parent = parent_ref.get_object()
                parent_name = str(parent.get("/T", ""))
                if parent_name not in radio_updates:
                    continue
                config = radio_updates[parent_name]
                crm_field = config.get("crm_field")
                if not crm_field:
                    continue
                contact_value = str(merged.get(crm_field, "")).strip().lower()
                options_map = config.get("radio_options", {})
                selected_choice = None
                for choice_val, match_vals in options_map.items():
                    if isinstance(match_vals, str):
                        match_vals = [match_vals]
                    if contact_value in [m.lower() for m in match_vals]:
                        selected_choice = choice_val
                        break
                if selected_choice:
                    ap = annot.get("/AP", {})
                    n_dict = ap.get("/N", {}) if ap else {}
                    option_keys = [str(k) for k in n_dict.keys()] if hasattr(n_dict, 'keys') else []
                    choice_name = NameObject(f"/{selected_choice}")
                    if choice_name in [NameObject(k) for k in option_keys]:
                        annot[NameObject("/AS")] = choice_name
                        parent[NameObject("/V")] = choice_name
                        fields_written += 1
                        logger.debug("  WROTE radio [page %d] %r = %s", page_idx + 1, parent_name, selected_choice)
                    else:
                        annot[NameObject("/AS")] = NameObject("/Off")

    if fields_written == 0:
        logger.warning("NO fields were written to the PDF!")
    else:
        logger.info("Written %d fields to PDF", fields_written)

    # Save output
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = contact.get("full_name", "unknown").replace(" ", "_")
    form_label = mapping.get("form_name", mapping_file).replace(" ", "_").replace("/", "-")
    output_filename = f"{safe_name}_{form_label}.pdf"
    output_path = OUTPUT_DIR / output_filename

    with open(output_path, "wb") as f:
        writer.write(f)

    output_size = output_path.stat().st_size
    logger.info("Output saved: %s (%d bytes)", output_path, output_size)

    if output_size < 1000:
        logger.warning("Output file suspiciously small (%d bytes) — may be corrupt", output_size)

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
