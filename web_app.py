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
from fastapi import FastAPI, Query, HTTPException
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
