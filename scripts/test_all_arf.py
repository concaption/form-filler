"""Final consolidated test: fill all 5 ARFs against multiple synthetic contacts.

Tests Sean Murphy (single-line address, full state/postcode), Noel Lourdes
(multi-line CRM address, no state/postcode — modelled on a real client that
broke v2.2.2), and Stefanie-style (single-line, no state/postcode).
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


def expand_address(base):
    """Synthesize the address_* derived fields the real crm_client.py produces.

    Mirrors the row distribution logic so the test harness exercises the same
    behaviour as a live OnePageCRM pull.
    """
    raw = base.get("address_line1", "") or ""
    city = base.get("address_city", "") or ""
    state = base.get("address_state", "") or ""
    postcode = base.get("address_postcode", "") or ""

    street_lines = [ln.strip() for ln in raw.replace("\r", "\n").split("\n") if ln.strip()]
    street_flat = ", ".join(street_lines)
    row1 = street_lines[0] if street_lines else ""
    extras = street_lines[1:] + ([city] if city else [])
    row2 = ", ".join(extras)
    row3 = ", ".join(p for p in [state, postcode] if p)

    base["address_line1"] = street_flat
    base["address_full"] = ", ".join(p for p in [street_flat, city, state, postcode] if p)
    base["address_county_postcode"] = ", ".join(p for p in [state, postcode] if p)
    base["address_city_county_postcode"] = ", ".join(p for p in [city, state, postcode] if p)
    base["address_line1_city"] = ", ".join(p for p in [street_flat, city] if p)
    base["address_row1"] = row1
    base["address_row2"] = row2
    base["address_row3"] = row3
    base["address_row2_row3"] = ", ".join(p for p in [row2, row3] if p)
    base["address_row1_row2"] = ", ".join(p for p in [row1, row2] if p)
    base["address_block"] = "\n".join(p for p in [row1, row2] if p)
    return base


sean_murphy = expand_address({
    "id": "test-sean", "full_name": "Sean Murphy",
    "first_name": "Sean", "last_name": "Murphy",
    "title": "Mr", "gender": "Male", "status": "Married",
    "email": "sean.murphy@example.ie",
    "phone_mobile": "+353 87 123 4567", "phone_work": "+353 1 555 0123",
    "birthday": "1979-02-02", "pps_1": "1234567A",
    "address_line1": "17 Merrion Square", "address_city": "Dublin 2",
    "address_state": "Co Dublin", "address_postcode": "D02 X285",
    "job_title": "Director", "company_name": "Murphy Holdings Ltd",
    "salary": "95000", "nra_age": "65",
})

# Real-world-style contact: multi-line CRM address, no state/postcode populated
noel_lourdes = expand_address({
    "id": "test-noel", "full_name": "Noel Lourdes",
    "first_name": "Noel", "last_name": "Lourdes",
    "title": "Mr", "gender": "Male", "status": "Married",
    "email": "noel.a.lourdes@gmail.com",
    "phone_mobile": "0876839509",
    "birthday": "1974-12-19", "pps_1": "8638709C",
    "address_line1": "12 Marlborough Road\r\nOxmantown\r\nSouth Circular Road",
    "address_city": "Dublin 7",
    "address_state": "", "address_postcode": "",
    "nationality": "Malaysian",
    "job_title": "Software Engineer",
})

# Stefanie-style contact: single-line address, no state/postcode (real CRM gap)
stefanie_like = expand_address({
    "id": "test-stef", "full_name": "Stefanie Mangan",
    "first_name": "Stefanie", "last_name": "Mangan",
    "title": "Mrs", "gender": "Female", "status": "Married",
    "email": "stefmangan@hotmail.com",
    "phone_mobile": "0879695612",
    "birthday": "1971-03-30", "pps_1": "9388015J",
    "address_line1": "Milltown", "address_city": "Kilcock",
    "address_state": "", "address_postcode": "",
    "nationality": "German",
})

ARFS = [
    ("aviva_arf.json",         "Aviva ARF/AMRF"),
    ("irish_life_arf.json",    "Irish Life Complete Solutions ARF"),
    ("zurich_arf.json",        "Zurich ARF"),
    ("davy_select_arf.json",   "Davy Select ARF (Execution-Only)"),
    ("standard_life_arf.json", "Standard Life Synergy ARF"),
    ("aviva_retirement_bond.json",     "Aviva Retirement Bond"),
    ("irish_life_prb.json",            "Irish Life PRB"),
    ("zurich_prb.json",                "Zurich PRB"),
    ("davy_retirement_account.json",   "Davy Retirement Account"),
    ("standard_life_bob.json",         "Standard Life Buy-Out Bond"),
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


CONTACTS = [
    ("Sean Murphy (full address)", sean_murphy, "fergal"),
    ("Noel Lourdes (multi-line, no state)", noel_lourdes, "liam"),
    ("Stefanie-like (single-line, no state)", stefanie_like, "liam"),
]

print(f"\n{'CONTACT / FORM':<55} {'mapped':>7} {'text':>5} {'boxes':>6}  OUTPUT")
print("-" * 130)

for contact_label, contact, adviser in CONTACTS:
    for mapping, display in ARFS:
        mapping_json = json.loads((Path('src/fieldmaps') / mapping).read_text())
        total_mapped = sum(1 for k, v in mapping_json['field_map'].items()
                           if not k.startswith('__') and isinstance(v, dict)
                           and (v.get('crm_field') or v.get('adviser_field') or v.get('match_value')
                                or v.get('radio_group')))
        try:
            out = fill_form(mapping, contact, adviser_id=adviser)
            txt, radio = count_filled(out)
            out_name = Path(out).name
            label = f"{contact_label} / {display}"
            print(f"{label:<55} {total_mapped:>7} {txt:>5} {radio:>6}  {out_name}")
        except Exception as e:
            print(f"{contact_label} / {display}  FAILED: {e!r}")
    print()
