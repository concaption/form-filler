# AutoFill - YourFinance.ie

Desktop application that auto-fills PDF application forms using contact data from OnePageCRM.

## What it does

1. Syncs contacts from OnePageCRM (8,000+)
2. Search for a contact by name
3. Select a form template (Aviva, Zurich, Irish Life)
4. Download a pre-filled PDF with client details populated

## Supported Forms

| Provider | Form | Product |
|----------|------|---------|
| Aviva | PRSA Application | PRSA |
| Aviva | Master Trust Employee | Master Trust |
| Aviva | Master Trust Employer | Master Trust |
| Aviva | Retail Master Trust | Retail Master Trust |
| Aviva | Multi-Product Application | Multi-Product |
| Irish Life | PRSA Application | PRSA |
| Irish Life | PRSA Transfer-In (Brokerage) | PRSA |
| Irish Life | Protection Application | Protection |
| Irish Life | Retail Master Trust CS2 | Retail Master Trust |
| Zurich | PRSA Application | PRSA |
| Zurich | Protection Application | Protection |
| Zurich | Master Trust Executive Pension | Master Trust |

## Setup

### Requirements

- Python 3.9+
- OnePageCRM API credentials

### Install

```bash
pip install -r requirements.txt
```

### Configure

Create a `.env` file:

```
USER_ID=your_onepagecrm_user_id
API_KEY=your_onepagecrm_api_key
```

### Run

**Web app (development):**

```bash
python web_app.py
```

Opens at http://localhost:8080

**Desktop app (Windows .exe):**

```bash
python build.py
```

Produces `dist/AutoFill.exe`. On first launch it creates an `AutoFill_Data` folder next to itself containing editable PDFs and field mappings.

## Project Structure

```
app.py                  # Desktop app (CustomTkinter)
web_app.py              # Web app (FastAPI)
crm_client.py           # OnePageCRM API client
pdf_filler.py           # PDF form filling engine (PyPDF2)
db.py                   # SQLite local contact cache
config.py               # Path configuration
build.py                # PyInstaller build script
pdfs/                   # Source PDF form templates
field_mappings/         # JSON field mapping configs
templates/              # HTML UI template
output/                 # Generated filled PDFs
```

## Field Mappings

Each form has a JSON mapping file in `field_mappings/` that maps PDF field names to CRM contact fields. Example:

```json
{
  "form_name": "Aviva PRSA Application Form",
  "pdf_file": "Aviva-PRSA-Application-Form.pdf",
  "field_map": {
    "Text Field 255": {
      "label": "First Name",
      "crm_field": "first_name"
    },
    "Check Box 90": {
      "label": "Title: Mr",
      "crm_field": "title",
      "match_value": "Mr"
    },
    "Text Field 200": {
      "label": "DOB Day",
      "crm_field": "birthday",
      "transform": "day"
    }
  }
}
```

- `crm_field`: CRM contact field name (`null` for broker-filled fields)
- `match_value`: For checkboxes, checks the box when the CRM value matches
- `transform`: Extract `day`, `month`, or `year` from a date field

## CRM Fields

Contact data pulled from OnePageCRM:

| CRM Field | Description |
|-----------|-------------|
| `first_name`, `last_name`, `full_name` | Name |
| `title` | Mr / Mrs / Ms |
| `birthday` | Date of birth (YYYY-MM-DD) |
| `pps_1` | PPS Number |
| `email` | Primary email |
| `phone_mobile`, `phone_home`, `phone_work` | Phone numbers |
| `address_line1`, `address_city`, `address_state`, `address_postcode` | Home address |
| `address_work_line1`, `address_work_city`, `address_work_full` | Work address |
| `company_name` | Employer name |
| `job_title` | Occupation |
| `salary` | Annual salary |
| `gender` | Male / Female |
| `status` | Marital status |
| `nationality`, `country_of_residence` | Nationality / Country |
| `employer_tax_number` | Employer tax reference |
| `start_date_for_current_employment` | Employment start date |
| `smoker` | Yes / No |

## CI/CD

GitHub Actions builds a Windows `.exe` on every push to `main`. Tagged releases (`v*`) create a GitHub Release with the `.exe` attached.

```bash
git tag v1.0.0
git push origin v1.0.0
```

Download from [Releases](../../releases/latest).
