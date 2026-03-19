"""FastAPI-based web version of Form Filler.

Run with:
    uvicorn web_app:app --reload --port 8080

Or:
    python web_app.py
"""

import os
import sys
import json
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from config import TEMPLATES_DIR, OUTPUT_DIR
from crm_client import list_all_contacts, iter_all_contacts, get_contact
from pdf_filler import fill_form, get_available_forms
from db import (
    save_contacts,
    search_contacts_local,
    list_contacts_local,
    get_contact_local,
    get_contact_count,
    get_last_sync,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="AutoFill - YourFinance.ie", version="1.0.0")

TEMPLATE_PATH = TEMPLATES_DIR / "index.html"


class GenerateRequest(BaseModel):
    contact_id: str
    form: str
    edits: dict = None


@app.get("/", response_class=HTMLResponse)
async def index():
    return TEMPLATE_PATH.read_text()


@app.get("/api/forms")
async def api_forms():
    return get_available_forms()


@app.get("/api/sync-info")
async def api_sync_info():
    return {"count": get_contact_count(), "last_sync": get_last_sync()}


@app.post("/api/sync")
async def api_sync():
    """Sync all contacts from OnePageCRM to local SQLite (non-streaming fallback)."""
    try:
        contacts = list_all_contacts()
        save_contacts(contacts)
        return {"count": len(contacts)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/sync-stream")
async def api_sync_stream():
    """Sync contacts with SSE progress updates."""
    def generate():
        all_contacts = []
        try:
            for page, max_page, batch in iter_all_contacts():
                all_contacts.extend(batch)
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "page": page,
                        "max_page": max_page,
                        "fetched": len(all_contacts),
                    }),
                }
            save_contacts(all_contacts)
            yield {
                "event": "done",
                "data": json.dumps({"count": len(all_contacts)}),
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
    return EventSourceResponse(generate())


@app.get("/api/settings")
async def api_get_settings():
    """Return current .env settings (masked API key)."""
    from dotenv import dotenv_values
    env_path = Path(__file__).parent / ".env"
    vals = dotenv_values(env_path) if env_path.exists() else {}
    api_key = vals.get("API_KEY", "")
    return {
        "user_id": vals.get("USER_ID", ""),
        "api_key": api_key,
    }


class SettingsRequest(BaseModel):
    user_id: str
    api_key: str


@app.post("/api/settings")
async def api_save_settings(req: SettingsRequest):
    """Update .env with new credentials and reload them."""
    env_path = Path(__file__).parent / ".env"
    env_path.write_text(f"API_KEY={req.api_key}\nUSER_ID={req.user_id}\n")
    # Reload into the running process
    import crm_client
    crm_client.USER_ID = req.user_id
    crm_client.API_KEY = req.api_key
    os.environ["USER_ID"] = req.user_id
    os.environ["API_KEY"] = req.api_key
    return {"ok": True}


@app.get("/api/contacts/search")
async def api_search(q: str = Query("")):
    if not q:
        return []
    return search_contacts_local(q)


@app.get("/api/contacts/local")
async def api_contacts_local():
    return list_contacts_local()


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    if not req.contact_id or not req.form:
        raise HTTPException(status_code=400, detail="Missing contact or form selection")

    contact = get_contact_local(req.contact_id)
    if not contact:
        contact = get_contact(req.contact_id)

    # Apply any inline edits from the UI
    if req.edits:
        contact.update(req.edits)

    try:
        output_path = fill_form(req.form, contact)
        filename = Path(output_path).name
        return {"filename": filename, "path": output_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{filename}")
async def download(filename: str):
    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        str(filepath),
        filename=filename,
        media_type="application/pdf",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/mapping-tool", response_class=HTMLResponse)
async def mapping_tool():
    return (TEMPLATES_DIR / "mapping_tool.html").read_text()


@app.post("/api/mapping-tool/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF and extract all form fields."""
    from PyPDF2 import PdfReader
    from PyPDF2.generic import ArrayObject
    import shutil

    # Save to src/pdfs/
    from config import PDFS_DIR
    dest = PDFS_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Extract fields
    reader = PdfReader(str(dest))
    fields = []
    for page_idx, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        annot_list = annots if isinstance(annots, ArrayObject) else annots.get_object()
        for ref in annot_list:
            annot = ref.get_object()
            name = str(annot.get("/T", ""))
            ftype = str(annot.get("/FT", ""))
            rect = annot.get("/Rect")
            y = float(rect[1]) if rect else 0
            x = float(rect[0]) if rect else 0
            max_len = annot.get("/MaxLen")
            # Check for parent (radio group child)
            parent = annot.get("/Parent")
            parent_name = ""
            if parent:
                p = parent.get_object()
                parent_name = str(p.get("/T", ""))
            if name or parent_name:
                fields.append({
                    "name": name or f"(child of {parent_name})",
                    "type": ftype.replace("/", ""),
                    "page": page_idx + 1,
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "max_len": int(max_len) if max_len else None,
                    "parent": parent_name,
                })

    return {
        "filename": file.filename,
        "pages": len(reader.pages),
        "fields": sorted(fields, key=lambda f: (f["page"], -f["y"], f["x"])),
    }


@app.get("/api/mapping-tool/fieldmap/{filename}")
async def fieldmap_pdf(filename: str):
    """Generate an annotated PDF with field names overlaid in red."""
    from config import PDFS_DIR, FIELDMAPS_PDFS_DIR
    from generate_field_maps import generate_field_map

    pdf_path = PDFS_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    output_path = FIELDMAPS_PDFS_DIR / f"fieldmap_{filename}"
    output_path.parent.mkdir(exist_ok=True)
    generate_field_map(pdf_path, output_path)

    return FileResponse(
        str(output_path),
        filename=f"fieldmap_{filename}",
        media_type="application/pdf",
    )


@app.post("/api/mapping-tool/save")
async def save_mapping(
    filename: str = Form(...),
    form_name: str = Form(...),
    provider: str = Form(...),
    product: str = Form(...),
    mapping_json: str = Form(...),
):
    """Save a field mapping JSON file."""
    from config import MAPPINGS_DIR
    import re

    # Generate a safe mapping filename
    safe = re.sub(r'[^a-z0-9]+', '_', provider.lower() + "_" + product.lower()).strip('_')
    mapping_path = MAPPINGS_DIR / f"{safe}.json"

    field_map = json.loads(mapping_json)
    data = {
        "form_name": form_name,
        "pdf_file": filename,
        "provider": provider,
        "product": product,
        "field_map": field_map,
    }

    with open(mapping_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    return {"ok": True, "path": str(mapping_path)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"

    url = f"http://localhost:{port}"
    print(f"\n  AutoFill Application (FastAPI) running at: {url}\n")
    print(f"  API docs at: {url}/docs\n")

    if not os.environ.get("PORT"):
        import webbrowser
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=host, port=port)
