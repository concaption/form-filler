"""Smoke test: fill the 5 new ARF forms with a synthetic Fergal contact + Fergal as adviser.

Not a semantic test — the ARF fieldmaps are scaffolds with crm_field=null on every
field, so we expect 0 fields to be written. This only verifies the pipeline loads
each mapping, opens the PDF, and writes an output file.
"""

import logging
from pdf_filler import fill_form

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

fergal_as_client = {
    "id": "test-fergal",
    "full_name": "Fergal Tully",
    "first_name": "Fergal",
    "last_name": "Tully",
    "title": "Mr",
    "gender": "Male",
    "email": "fergal@yourfinance.ie",
    "phone_mobile": "+353 87 000 0000",
    "phone_work": "+353 1 000 0000",
    "company_name": "Your Finance",
    "job_title": "Director",
    "address_line1": "1 Main Street",
    "address_city": "Dublin",
    "birthday": "1975-01-01",
    "pps_1": "1234567A",
    "status": "Married",
    "salary": "75000",
    "nra_age": "65",
}

ARFS = [
    "aviva_arf.json",
    "irish_life_arf.json",
    "zurich_arf.json",
    "davy_select_arf.json",
    "standard_life_arf.json",
]

print()
for mapping in ARFS:
    print(f"\n{'=' * 60}\n  {mapping}\n{'=' * 60}")
    try:
        out = fill_form(mapping, fergal_as_client, adviser_id="fergal")
        print(f"  OK  -> {out}")
    except Exception as e:
        print(f"  FAIL -> {e!r}")
