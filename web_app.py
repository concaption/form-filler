"""FastAPI-based web version of Form Filler.

Run with:
    uvicorn web_app:app --reload --port 8080

Or:
    python web_app.py
"""

import os
import sys
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

# Ensure we're running from the project directory
os.chdir(Path(__file__).parent)

from crm_client import list_all_contacts, get_contact
from pdf_filler import fill_form, get_available_forms, OUTPUT_DIR
from db import (
    save_contacts,
    search_contacts_local,
    list_contacts_local,
    get_contact_local,
    get_contact_count,
    get_last_sync,
)

app = FastAPI(title="AutoFill - Your Finance", version="1.0.0")


class GenerateRequest(BaseModel):
    contact_id: str
    form: str


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AutoFill - Your Finance</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
         background: #f0f2f5; color: #333; }
  .header { background: linear-gradient(135deg, #1a365d, #2d5a8e); color: #fff;
             padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 22px; font-weight: 600; }
  .header .subtitle { font-size: 12px; opacity: 0.8; }
  .sync-bar { background: #fff; border-bottom: 1px solid #e2e8f0; padding: 10px 24px;
              display: flex; align-items: center; gap: 12px; font-size: 13px; }
  .sync-info { color: #666; flex: 1; }
  .sync-info strong { color: #1a365d; }
  .container { max-width: 960px; margin: 0 auto; padding: 20px; }
  .card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.06); border: 1px solid #e8e8e8; }
  .card h2 { font-size: 14px; color: #1a365d; margin-bottom: 12px; text-transform: uppercase;
             letter-spacing: 0.5px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }
  .search-row { display: flex; gap: 8px; }
  .search-row input { flex: 1; padding: 10px 14px; border: 1px solid #ddd;
                      border-radius: 6px; font-size: 14px; outline: none; }
  .search-row input:focus { border-color: #2d5a8e; box-shadow: 0 0 0 2px rgba(45,90,142,0.15); }
  .btn { padding: 9px 18px; border: none; border-radius: 6px; font-size: 13px;
         cursor: pointer; font-weight: 500; transition: all 0.15s; }
  .btn-primary { background: #2d5a8e; color: #fff; }
  .btn-primary:hover { background: #1a365d; }
  .btn-sync { background: #38a169; color: #fff; }
  .btn-sync:hover { background: #2f855a; }
  .btn-secondary { background: #e8e8e8; color: #555; }
  .btn-secondary:hover { background: #ddd; }
  .btn-success { background: #38a169; color: #fff; font-size: 15px; padding: 12px 32px; }
  .btn-success:hover { background: #2f855a; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .contact-list { list-style: none; max-height: 220px; overflow-y: auto;
                  border: 1px solid #eee; border-radius: 6px; margin-top: 10px; }
  .contact-list li { padding: 10px 14px; border-bottom: 1px solid #f0f0f0;
                     cursor: pointer; font-size: 13px; transition: background 0.1s;
                     display: flex; justify-content: space-between; }
  .contact-list li:hover { background: #f0f5ff; }
  .contact-list li.selected { background: #e1ecf7; font-weight: 500; }
  .contact-list li:last-child { border-bottom: none; }
  .contact-name { font-weight: 500; }
  .contact-meta { color: #888; font-size: 12px; }
  .details-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 20px; font-size: 13px; }
  .details-grid .label { color: #888; }
  .details-grid .value { font-weight: 500; }
  .form-select { width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 6px;
                 font-size: 14px; outline: none; background: #fff; }
  .form-select:focus { border-color: #2d5a8e; }
  .status { margin-top: 12px; padding: 10px 14px; border-radius: 6px;
            font-size: 13px; display: none; }
  .status.info { display: block; background: #ebf8ff; color: #2b6cb0; }
  .status.success { display: block; background: #f0fff4; color: #276749; }
  .status.error { display: block; background: #fff5f5; color: #c53030; }
  .output-files { margin-top: 10px; }
  .output-files a { display: inline-block; margin: 4px 8px 4px 0; padding: 8px 14px;
                    background: #ebf8ff; color: #2b6cb0; border-radius: 4px;
                    text-decoration: none; font-size: 13px; font-weight: 500; }
  .output-files a:hover { background: #bee3f8; }
  .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid currentColor;
             border-top-color: transparent; border-radius: 50%;
             animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .empty { color: #999; font-style: italic; padding: 20px; text-align: center; }
  .actions-row { display: flex; gap: 10px; align-items: center; justify-content: center; margin: 20px 0; }
  .save-path { margin-top: 8px; font-size: 12px; color: #666; word-break: break-all; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>AutoFill Application</h1>
    <div class="subtitle">Your Finance - Form Automation</div>
  </div>
</div>

<div class="sync-bar">
  <button class="btn btn-sync" id="syncBtn" onclick="syncContacts()">Sync Contacts</button>
  <div class="sync-info" id="syncInfo">Loading...</div>
</div>

<div class="container">
  <div class="card">
    <h2>Step 1: Select Client</h2>
    <div class="search-row">
      <input type="text" id="searchInput" placeholder="Type to search contacts..."
             oninput="liveSearch()" onkeydown="if(event.key==='Enter') liveSearch()">
      <button class="btn btn-secondary" onclick="loadAll()">Show All</button>
    </div>
    <ul class="contact-list" id="contactList">
      <li class="empty">Sync contacts first, then search or show all</li>
    </ul>
  </div>

  <div class="card" id="detailsCard" style="display:none">
    <h2>Step 2: Client Details</h2>
    <div class="details-grid" id="detailsGrid"></div>
  </div>

  <div class="card" id="formsCard" style="display:none">
    <h2>Step 3: Select Application Form</h2>
    <select class="form-select" id="formSelect">
      <option value="">-- Select a template --</option>
    </select>
  </div>

  <div class="actions-row" id="generateSection" style="display:none">
    <button class="btn btn-success" id="generateBtn" onclick="fillAndSave()">
      Fill &amp; Save As
    </button>
  </div>

  <div class="status" id="statusBar"></div>
  <div class="output-files" id="outputFiles"></div>
</div>

<script>
let contacts = [];
let selectedContact = null;
let searchTimer = null;

window.addEventListener('DOMContentLoaded', () => {
  loadFormTemplates();
  loadSyncInfo();
});

function loadFormTemplates() {
  fetch('/api/forms').then(r => r.json()).then(data => {
    const sel = document.getElementById('formSelect');
    data.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.mapping_file;
      opt.textContent = f.provider + ' - ' + f.product;
      sel.appendChild(opt);
    });
  });
}

function loadSyncInfo() {
  fetch('/api/sync-info').then(r => r.json()).then(data => {
    const info = document.getElementById('syncInfo');
    if (data.count > 0) {
      const syncDate = new Date(data.last_sync).toLocaleString();
      info.innerHTML = '<strong>' + data.count + '</strong> contacts synced | Last sync: ' + syncDate;
    } else {
      info.textContent = 'No contacts synced yet. Click "Sync Contacts" to get started.';
    }
  });
}

function setStatus(msg, type) {
  const bar = document.getElementById('statusBar');
  bar.className = 'status ' + type;
  bar.textContent = msg;
}

function syncContacts() {
  const btn = document.getElementById('syncBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Syncing...';
  setStatus('Syncing contacts from OnePageCRM... This may take a moment.', 'info');

  fetch('/api/sync', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        setStatus('Sync failed: ' + data.error, 'error');
      } else {
        setStatus('Synced ' + data.count + ' contacts successfully!', 'success');
        loadSyncInfo();
      }
    })
    .catch(e => setStatus('Sync failed: ' + e, 'error'))
    .finally(() => { btn.disabled = false; btn.textContent = 'Sync Contacts'; });
}

function liveSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const query = document.getElementById('searchInput').value.trim();
    if (query.length < 2) return;
    fetch('/api/contacts/search?q=' + encodeURIComponent(query))
      .then(r => r.json())
      .then(data => { contacts = data; renderContacts(); });
  }, 300);
}

function loadAll() {
  setStatus('Loading all contacts...', 'info');
  fetch('/api/contacts/local')
    .then(r => r.json())
    .then(data => {
      contacts = data;
      renderContacts();
      if (data.length === 0) {
        setStatus('No contacts found. Please sync first.', 'info');
      } else {
        setStatus('Showing ' + data.length + ' contacts.', 'info');
      }
    });
}

function renderContacts() {
  const list = document.getElementById('contactList');
  list.innerHTML = '';
  if (contacts.length === 0) {
    list.innerHTML = '<li class="empty">No contacts found</li>';
    return;
  }
  contacts.forEach((c, i) => {
    const li = document.createElement('li');
    li.innerHTML = '<span class="contact-name">' + escapeHtml(c.full_name) + '</span>' +
                   '<span class="contact-meta">' + escapeHtml(c.email || '') +
                   (c.company_name ? ' | ' + escapeHtml(c.company_name) : '') + '</span>';
    li.onclick = () => selectContact(i);
    list.appendChild(li);
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function selectContact(idx) {
  selectedContact = contacts[idx];
  document.querySelectorAll('.contact-list li').forEach((li, i) => {
    li.className = i === idx ? 'selected' : '';
  });

  const grid = document.getElementById('detailsGrid');
  grid.innerHTML = '';
  const fields = [
    ['Name', 'full_name'], ['Title', 'title'], ['DOB', 'date_of_birth'],
    ['PPS Number', 'pps_number'], ['Email', 'email'], ['Mobile', 'phone_mobile'],
    ['Phone', 'phone'], ['Address', 'address_full'],
    ['Occupation', 'occupation'], ['Job Title', 'job_title'],
    ['Employer', 'employer_name'], ['Marital Status', 'marital_status'],
    ['Employment', 'employment_type'], ['Annual Income', 'annual_income'],
    ['NRA', 'normal_retirement_age'], ['Nationality', 'nationality'],
    ['IBAN', 'iban'], ['BIC', 'bic']
  ];
  fields.forEach(([label, key]) => {
    const val = selectedContact[key] || '';
    if (val) {
      grid.innerHTML += '<span class="label">' + escapeHtml(label) +
                        '</span><span class="value">' + escapeHtml(String(val)) + '</span>';
    }
  });

  document.getElementById('detailsCard').style.display = '';
  document.getElementById('formsCard').style.display = '';
  document.getElementById('generateSection').style.display = '';
  setStatus('Selected: ' + selectedContact.full_name, 'info');
}

function fillAndSave() {
  if (!selectedContact) return;
  const formSelect = document.getElementById('formSelect');
  const mappingFile = formSelect.value;
  if (!mappingFile) { setStatus('Please select a template first.', 'error'); return; }

  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating...';
  setStatus('Filling form...', 'info');
  document.getElementById('outputFiles').innerHTML = '';

  fetch('/api/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ contact_id: selectedContact.id, form: mappingFile })
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) {
      setStatus('Error: ' + data.error, 'error');
      return;
    }
    setStatus('Form generated successfully!', 'success');
    const div = document.getElementById('outputFiles');
    const a = document.createElement('a');
    a.href = '/download/' + encodeURIComponent(data.filename);
    a.textContent = 'Download: ' + data.filename;
    div.appendChild(a);
    const p = document.createElement('p');
    p.className = 'save-path';
    p.textContent = 'Saved to: ' + data.path;
    div.appendChild(p);
  })
  .catch(e => setStatus('Generation failed: ' + e, 'error'))
  .finally(() => { btn.disabled = false; btn.innerHTML = 'Fill &amp; Save As'; });
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_TEMPLATE


@app.get("/api/forms")
async def api_forms():
    return get_available_forms()


@app.get("/api/sync-info")
async def api_sync_info():
    return {"count": get_contact_count(), "last_sync": get_last_sync()}


@app.post("/api/sync")
async def api_sync():
    """Sync all contacts from OnePageCRM to local SQLite."""
    try:
        contacts = list_all_contacts()
        save_contacts(contacts)
        return {"count": len(contacts)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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
    return FileResponse(str(filepath), filename=filename)


if __name__ == "__main__":
    import webbrowser
    import threading

    port = 8080
    url = f"http://localhost:{port}"
    print(f"\n  AutoFill Application (FastAPI) running at: {url}\n")
    print(f"  API docs at: {url}/docs\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port)
