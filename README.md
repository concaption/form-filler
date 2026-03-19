# AutoFill - YourFinance.ie

Desktop and web application that auto-fills PDF application forms using contact data from OnePageCRM.

## Features

- Sync 8,000+ contacts from OnePageCRM with real-time progress
- Search and select contacts, review and edit details before filling
- Fill PDF forms with one click across 13 supported templates
- Save As dialog to choose output location
- Built-in Mapping Tool to add new PDF forms without code
- Settings UI to update CRM credentials
- Windows `.exe` build via GitHub Actions

## Supported Forms

| Provider | Product |
|----------|---------|
| Aviva | PRSA, Master Trust Employee, Master Trust Employer, Retail Master Trust, Multi-Product |
| Irish Life | PRSA, PRSA Transfer-In (Brokerage), Protection, Retail Master Trust CS2 |
| Zurich | PRSA, Protection, Master Trust Executive Pension |
| Standard Life | Synergy PRSA |

## Setup

### Requirements

- Python 3.9+
- OnePageCRM API credentials

### Install

```bash
pip install -r requirements.txt
```

### Configure

Create a `.env` file (or use the Settings button in the app):

```
USER_ID=your_onepagecrm_user_id
API_KEY=your_onepagecrm_api_key
```

### Run

**Desktop app:**

```bash
python app.py
```

**Web app:**

```bash
python web_app.py
```

Opens at http://localhost:8080

**Windows .exe:**

Download from [Releases](../../releases/latest), or build locally:

```bash
python build.py
```

On first launch, `AutoFill.exe` creates an `AutoFill_Data` folder next to itself containing editable PDFs and field mappings.

## Adding New Forms

### Using the Mapping Tool (recommended)

1. Click **Mapping Tool** in the app header
2. Browse and select the PDF form
3. Click **Open Field Map PDF** to see field names overlaid on the form
4. Map each PDF field to a CRM field using the dropdown
5. Fill in Provider, Product, and Form Name
6. Click **Save Mapping**

The new form appears in the dropdown immediately.

### Manual mapping

1. Place the PDF in `pdfs/`
2. Run `python generate_field_maps.py` to create an annotated reference PDF
3. Create a JSON file in `field_mappings/`:

```json
{
  "form_name": "Provider Product Application",
  "pdf_file": "form-filename.pdf",
  "provider": "Provider",
  "product": "Product",
  "field_map": {
    "PDF Field Name": {
      "label": "Human-readable label",
      "crm_field": "crm_field_name"
    }
  }
}
```

## Field Mapping Options

| Option | Description | Example |
|--------|-------------|---------|
| `crm_field` | CRM field name, or `null` for manual fields | `"first_name"` |
| `match_value` | For checkboxes: check when CRM value matches | `"Mr"` |
| `transform` | Transform the value before filling | `"day"`, `"month"`, `"year"` |
| | | `"date_ddmmyyyy"`, `"date_ddmmyyyy_noslash"` |
| | | `"email_prefix"`, `"email_domain"` |
| | | `"strip_spaces"` |
| `radio_group` | Mark as radio button group with child widgets | `true` |
| `radio_options` | Map radio choices to CRM values | `{"Choice1": ["Single"]}` |

## CRM Fields

| Field | Description |
|-------|-------------|
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

## Project Structure

```
app.py                  # Desktop app (CustomTkinter)
web_app.py              # Web app (FastAPI)
crm_client.py           # OnePageCRM API client
pdf_filler.py           # PDF form filling engine (PyPDF2)
db.py                   # SQLite local contact cache
config.py               # Path configuration
build.py                # PyInstaller build script
generate_field_maps.py  # Annotated PDF generator for field identification
pdfs/                   # Source PDF form templates
field_mappings/         # JSON field mapping configs
templates/              # HTML UI templates
output/                 # Generated filled PDFs
```

## CI/CD

GitHub Actions builds a Windows `.exe` on every push to `main`. Tagged releases (`v*`) create a GitHub Release with the `.exe` attached.

```bash
git tag v1.5.0
git push origin v1.5.0
```

Download from [Releases](../../releases/latest).
