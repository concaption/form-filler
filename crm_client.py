"""OnePageCRM API client for fetching contact data."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://app.onepagecrm.com/api/v3"
USER_ID = os.getenv("USER_ID", "")
API_KEY = os.getenv("API_KEY", "")


def _auth():
    return (USER_ID, API_KEY)


def get_custom_field_map():
    """Fetch custom field definitions and return {id: name} mapping."""
    resp = requests.get(f"{API_BASE}/custom_fields.json", auth=_auth(), params={"per_page": 100})
    resp.raise_for_status()
    data = resp.json()
    mapping = {}
    for cf in data.get("data", {}).get("custom_fields", []):
        f = cf["custom_field"]
        mapping[f["id"]] = f["name"]
    return mapping


def search_contacts(query: str) -> list[dict]:
    """Search contacts by name. Returns a list of simplified contact dicts."""
    resp = requests.get(
        f"{API_BASE}/contacts.json",
        auth=_auth(),
        params={"search": query, "per_page": 20},
    )
    resp.raise_for_status()
    data = resp.json()

    cf_map = get_custom_field_map()
    results = []
    for item in data.get("data", {}).get("contacts", []):
        c = item["contact"]
        contact = _parse_contact(c, cf_map)
        results.append(contact)
    return results


def get_contact(contact_id: str) -> dict:
    """Fetch a single contact by ID with all custom fields resolved."""
    resp = requests.get(f"{API_BASE}/contacts/{contact_id}.json", auth=_auth())
    resp.raise_for_status()
    data = resp.json()
    c = data["data"]["contact"]
    cf_map = get_custom_field_map()
    return _parse_contact(c, cf_map)


def _parse_contact(c: dict, cf_map: dict) -> dict:
    """Parse raw API contact into a flat dict with friendly field names."""
    # Basic fields
    contact = {
        "id": c.get("id", ""),
        "title": c.get("title", ""),
        "first_name": c.get("first_name", ""),
        "last_name": c.get("last_name", ""),
        "full_name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
        "job_title": c.get("job_title", ""),
        "company_name": c.get("company_name", ""),
    }

    # Emails
    for email in c.get("emails", []):
        etype = email.get("type", "work")
        contact[f"email_{etype}"] = email.get("value", "")
    if c.get("emails"):
        contact["email"] = c["emails"][0].get("value", "")

    # Phones
    for phone in c.get("phones", []):
        ptype = phone.get("type", "work")
        contact[f"phone_{ptype}"] = phone.get("value", "")
    if c.get("phones"):
        contact["phone"] = c["phones"][0].get("value", "")

    # Address
    for addr in c.get("address_list", []):
        atype = addr.get("type", "home")
        prefix = f"address_{atype}" if atype != "home" else "address"
        contact[f"{prefix}_line1"] = addr.get("address", "")
        contact[f"{prefix}_city"] = addr.get("city", "")
        contact[f"{prefix}_state"] = addr.get("state", "")
        contact[f"{prefix}_postcode"] = addr.get("zip_code", "")
        contact[f"{prefix}_country"] = addr.get("country_code", "")
        # Full address string
        parts = [addr.get("address", ""), addr.get("city", ""), addr.get("state", ""), addr.get("zip_code", "")]
        contact[f"{prefix}_full"] = ", ".join(p for p in parts if p)

    # Custom fields — value is a sibling of custom_field, not nested inside it
    for cf in c.get("custom_fields", []):
        cf_data = cf.get("custom_field", {})
        cf_id = cf_data.get("id", "")
        cf_value = cf.get("value", "")  # value is on the outer object
        cf_name = cf_map.get(cf_id, cf_id)
        # Normalize the name to a key: "PPS Number" -> "pps_number"
        key = cf_name.lower().replace(" ", "_").replace("-", "_")
        contact[key] = cf_value

    return contact


def list_all_contacts() -> list[dict]:
    """Fetch all contacts (paginated)."""
    cf_map = get_custom_field_map()
    all_contacts = []
    page = 1
    while True:
        resp = requests.get(
            f"{API_BASE}/contacts.json",
            auth=_auth(),
            params={"page": page, "per_page": 100},
        )
        resp.raise_for_status()
        data = resp.json()
        contacts = data.get("data", {}).get("contacts", [])
        if not contacts:
            break
        for item in contacts:
            c = item["contact"]
            all_contacts.append(_parse_contact(c, cf_map))
        if page >= data.get("data", {}).get("max_page", 1):
            break
        page += 1
    return all_contacts


if __name__ == "__main__":
    # Quick test
    contacts = list_all_contacts()
    for c in contacts:
        print(f"\n--- {c['full_name']} ---")
        for k, v in sorted(c.items()):
            if v:
                print(f"  {k}: {v}")
