"""Fill Aviva ARF with adviser=Fergal + synthetic client (Sean Murphy) and verify output."""

import json
import logging
import sys
from pathlib import Path
from PyPDF2 import PdfReader
from PyPDF2.generic import ArrayObject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pdf_filler import fill_form

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

sean_murphy = {
    "id": "test-sean",
    "full_name": "Sean Murphy",
    "first_name": "Sean",
    "last_name": "Murphy",
    "title": "Mr",
    "gender": "Male",
    "status": "Married",
    "email": "sean.murphy@example.ie",
    "phone_mobile": "+353 87 123 4567",
    "phone_work": "+353 1 555 0123",
    "birthday": "1979-02-02",
    "pps_1": "1234567A",
    "address_line1": "17 Merrion Square",
    "address_city": "Dublin 2",
    "company_name": "Murphy Holdings Ltd",
    "job_title": "Director",
    "salary": "95000",
    "nra_age": "65",
}

output = fill_form("aviva_arf.json", sean_murphy, adviser_id="fergal")
print(f"\nOutput: {output}")

# Verify filled values by reading back the output PDF
reader = PdfReader(output)
filled = {}
for page in reader.pages:
    annots = page.get("/Annots")
    if not annots:
        continue
    annot_list = annots if isinstance(annots, ArrayObject) else annots.get_object()
    for aref in annot_list:
        a = aref.get_object()
        name = str(a.get("/T", ""))
        v = a.get("/V")
        asv = a.get("/AS")
        if name and (v is not None or asv is not None):
            filled[name] = {"V": str(v) if v else None, "AS": str(asv) if asv else None}

print(f"\nFields actually written: {len(filled)}")
print("\nBroker section (page 1):")
for k in ["Text Field 38", "Text Field 39", "Text Field 40", "Text Field 41", "Text Field 42"]:
    print(f"  {k:20s} -> {filled.get(k, '(empty)')}")

print("\nPersonal details (page 2):")
for k in ["Text Field 145", "Text Field 144", "Text Field 143", "Text Field 142", "Text Field 141",
         "Text Field 140", "Text Field 139", "Text Field 137", "Text Field 136", "Text Field 135"]:
    print(f"  {k:20s} -> {filled.get(k, '(empty)')}")

print("\nTitle/Gender/Status checkboxes:")
for k in ["Check Box 54", "Check Box 53", "Check Box 52", "Check Box 51", "Check Box 50",
         "Check Box 49", "Check Box 48", "Check Box 47"]:
    print(f"  {k:20s} -> {filled.get(k, '(empty)')}")
