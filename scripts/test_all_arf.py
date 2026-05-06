"""Final consolidated test: fill all 5 ARFs with Fergal + synthetic Sean Murphy.

Reports per-form: number of fields written, and verifies the output opens.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pdf_filler import fill_form
from PyPDF2 import PdfReader
from PyPDF2.generic import ArrayObject

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

sean_murphy = {
    "id": "test-sean", "full_name": "Sean Murphy",
    "first_name": "Sean", "last_name": "Murphy",
    "title": "Mr", "gender": "Male", "status": "Married",
    "email": "sean.murphy@example.ie",
    "phone_mobile": "+353 87 123 4567", "phone_work": "+353 1 555 0123",
    "birthday": "1979-02-02", "pps_1": "1234567A",
    "address_line1": "17 Merrion Square", "address_city": "Dublin 2",
    "job_title": "Director", "company_name": "Murphy Holdings Ltd",
    "salary": "95000", "nra_age": "65",
}
# Note: nationality/country defaults now come from static_value in each fieldmap.
# To override per-contact, pass extra_fields={"nationality": "French", ...} to fill_form.

ARFS = [
    ("aviva_arf.json",         "Aviva ARF/AMRF"),
    ("irish_life_arf.json",    "Irish Life Complete Solutions ARF"),
    ("zurich_arf.json",        "Zurich ARF"),
    ("davy_select_arf.json",   "Davy Select ARF (Execution-Only)"),
    ("standard_life_arf.json", "Standard Life Synergy ARF"),
]


def count_filled(pdf_path):
    """Count text fields with /V set and radios/checkboxes with /AS != /Off."""
    r = PdfReader(pdf_path)
    text_filled = 0
    radio_filled = 0
    for page in r.pages:
        annots = page.get("/Annots")
        if not annots:
            continue
        annot_list = annots if isinstance(annots, ArrayObject) else annots.get_object()
        for aref in annot_list:
            try:
                a = aref.get_object()
            except Exception:
                continue
            if not hasattr(a, 'get'):
                continue
            v = a.get("/V")
            asv = a.get("/AS")
            ftype = str(a.get("/FT", ""))
            if ftype == "/Tx" and v:
                text_filled += 1
            elif asv and str(asv) != "/Off":
                radio_filled += 1
    return text_filled, radio_filled


print(f"\n{'FORM':<40} {'PDF fields':>12} {'Text':>6} {'✓boxes':>8}  OUTPUT")
print("-" * 110)

for mapping, display in ARFS:
    mapping_json = json.loads((Path('src/fieldmaps') / mapping).read_text())
    total_mapped = sum(1 for k, v in mapping_json['field_map'].items()
                       if not k.startswith('__') and isinstance(v, dict)
                       and (v.get('crm_field') or v.get('adviser_field') or v.get('match_value')
                            or v.get('radio_group')))
    try:
        out = fill_form(mapping, sean_murphy, adviser_id="fergal")
        txt, radio = count_filled(out)
        out_name = Path(out).name
        print(f"{display:<40} {total_mapped:>12} {txt:>6} {radio:>8}  {out_name}")
    except Exception as e:
        print(f"{display:<40}  FAILED: {e!r}")
